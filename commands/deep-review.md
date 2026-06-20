---
description: Run the periodic review suite — all five reviews with a compiled master summary, or a single area. Codebase health, frontend health, architecture, product health, README drift.
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit
---

# Deep review — periodic review suite

Run periodic reviews against the current codebase on main. With no argument, runs all five and compiles a master summary — the "run everything" maintenance cycle. With an area argument, runs just that one review at its own cadence (e.g. architecture quarterly without the other four).

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Area argument

`$ARGUMENTS` — optional. Empty means the full sweep. Otherwise match it to one area:

| Keyword | `subagent_type` | What it reviews | Report path |
|---------|-----------------|-----------------|-------------|
| `codebase` (or `health`) | `review-codebase-health` | Architecture coherence, tech debt, dependency health, test health, API consistency | `docs/jaqal/health-reviews/YYYY-MM-DD-health-review.md` |
| `frontend` | `review-frontend-health` | Design system consistency, accessibility, frontend code quality, responsive spot-check | `docs/jaqal/frontend-reviews/YYYY-MM-DD-frontend-review.md` |
| `architecture` (or `arch`) | `review-architecture` | Dependency map, boundaries, complexity, evolution readiness, data layer | `docs/jaqal/architecture-reviews/YYYY-MM-DD-architecture-review.md` |
| `product` | `review-product-health` | PRODUCT.md accuracy, product coherence, onboarding path, proposed PRODUCT.md updates | `docs/jaqal/product-reviews/YYYY-MM-DD-product-review.md` |
| `readme` | `review-readme` | README drift: stale claims, missing features, broken commands/paths/links, voice drift, proposed diff | `docs/jaqal/readme-reviews/YYYY-MM-DD-readme-review.md` |

If `$ARGUMENTS` is non-empty but matches no keyword, list the valid keywords and stop.

## Single-area run (argument given)

Spawn the one matching agent with the Task tool. It already knows its full workflow — just tell it the project path and today's date. When it returns, surface its report. Skip Phase 2 — there's nothing to cross-reference in a single review.

## Full sweep (no argument)

### Phase 1 — Run all five reviews in parallel

Spawn all five subagents simultaneously with the Task tool — do not run them sequentially. Use the `subagent_type` values from the table above. Each agent already knows its full workflow — just tell it the project path and today's date. Run all five with `run_in_background: true`.

### Phase 2 — Compile master summary

After all five reviews complete, read all five reports and synthesize a single master summary.

#### Cross-review findings

Identify findings that appear in multiple reviews. These are systemic issues, not isolated ones — they get elevated priority. For example:
- Architecture review flags coupling AND codebase health flags related tech debt = systemic issue
- Product review flags a feature as low-value AND frontend review flags its code as complex = removal candidate
- Frontend review flags design drift AND product review flags persona drift = alignment problem
- README review flags a documented feature that no longer exists AND product review flags scope creep = the product moved and nothing tracked it

#### Prioritized action plan

Compile a single prioritized list across all five reviews:

**Critical (this week)**
All critical findings from every review, deduplicated and ordered by impact.

**Important (this month)**
All important findings, grouped by theme rather than by which review found them.

**Track (next review cycle)**
Items to monitor. Note which review surfaced each one so you know where to check progress.

#### Context doc updates

Based on the reviews, list specific updates needed for each context doc (per the maintenance workflow):
- **PRODUCT.md** — changes proposed by product health review
- **DESIGN.md** — changes proposed by frontend health review
- **CLAUDE.md** — changes proposed by architecture review
- **README.md** — diff proposed by README drift review

Do NOT apply these changes. Present them as proposed diffs for the user to review and approve.

#### Metrics dashboard

Pull the metrics snapshots from the codebase health and frontend health reports into a single table for easy trend tracking:

| Metric | Value | Trend vs last review | Source |
|--------|-------|---------------------|--------|
| Lines of code | — | — | codebase health |
| Test coverage | — | — | codebase health |
| TODO/FIXME count | — | — | codebase health |
| Outdated deps | — | — | codebase health |
| Known vulnerabilities | — | — | codebase health |
| Largest file (lines) | — | — | codebase health |
| Deepest dependency chain | — | — | codebase health |
| Component count | — | — | frontend health |
| Largest CSS file | — | — | frontend health |
| Accessibility issues (by severity) | — | — | frontend health |
| Design system deviations | — | — | frontend health |

Every row maps to a metric one of the two health reports actually emits — don't add rows no agent produces.

If previous review reports exist in the `docs/jaqal/` subdirectories, compare against the most recent one and fill in the trend column. Otherwise mark as "baseline".

Save the master summary to `docs/jaqal/health-reviews/YYYY-MM-DD-deep-review-summary.md`.
