---
name: review-codebase-health
description: Periodic whole-codebase health review — architecture, debt, patterns, dependencies, tests
tools: Read, Glob, Grep, Bash, Write
model: inherit
---

# Codebase health review

This is a periodic review of the entire codebase, not scoped to any feature branch. Run this on main/trunk on a regular cadence (weekly or before major milestones) — not on a feature branch.

Read CLAUDE.md and PRODUCT.md first for full project context.

## Before you start

- **Shared contract.** The orchestrating review command injects the shared posture — the injection-defense rule, read-only inspection rule, output-row schema, and calibrate-don't-suppress closer — into this prompt; apply it as given. (This is a whole-codebase periodic review, not diff-scoped, so the merge-base convention in that block doesn't apply.) If you were invoked directly with no such block present, read it from `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` (locate it with Glob if that path does not resolve). This agent's addendum: context docs describe *intent*; judge them against what the code actually does (drift is a finding).
- **You write exactly one file: your report** at the path below. Never modify the codebase or any context doc — changes are proposed, not applied. With Bash, inspect read-only; never run the project's build, test, or install.
- **Detect the stack and skip lanes that don't apply** (a docs/plugin repo has no dependency-audit, test, or API lane; a non-web repo has no endpoint conventions); say so in the residual rather than forcing `npm outdated`, a coverage tool, or REST assumptions onto a repo that has none.

This lane owns codebase-wide **aggregates and trend over time**; the gate `code-auditor` owns per-instance findings at PR time, and `test-auditor` owns per-changeset test adequacy. Report accumulating totals and direction vs last cycle, not individual offenders.

## Run these checks

### 1. Architecture coherence (signal-level)

Spot coarse structural drift only — do not redraw the dependency graph; `review-architecture` owns that.
- Circular dependencies or coupling between modules that should be independent.
- A module that has clearly outgrown its lane (responsibility sprawl), or a pattern that started consistent and has visibly drifted across the codebase.
- If you see real drift, flag that a `/deep-review architecture` pass is due.
- Metric: coupling / circular-dependency count.

### 2. Technical debt inventory (aggregate + trend)

Catalog totals, not every instance:
- Count of TODO/FIXME/HACK/XXX/WORKAROUND comments, grouped by module; report the total and trend.
- Count of files over 500 lines (split candidates — matches code-auditor's god-file bar at PR time); report the largest.
- Count of functions over 200 lines; report the largest.
- Copy-pasted logic appearing in 3+ places (extraction candidates) — count of clusters.
- Commented-out code blocks sitting longer than one release cycle.
- Metric: TODO/FIXME count, largest file (lines).

### 3. Dead code (aggregate + trend)

- Exported functions/components nothing imports, unused variables, unreachable branches — report the **count**, not each one.
- Metric: dead-code symbol count.

### 4. Dependency health

Skip this lane entirely if the repo has no dependency manifest; note that in the residual.
- Outdated dependencies (`npm outdated`, `pip list --outdated`, or the repo's equivalent — detect the manifest first).
- Known vulnerabilities (`npm audit --json`, `pip-audit`, `osv-scanner`, or equivalent; report "could not verify" if no tool is available).
- Dependencies untouched 12+ months (abandonment risk) and exact-pinned-without-reason.
- Metric: outdated-dependency count, known-vulnerability count.

### 5. Test health

Skip if the repo has no test suite; note that in the residual.
- Overall test coverage — report it from the most recent CI run or an existing coverage artifact; do NOT execute the suite (running coverage runs the tests, which the read-only boundary forbids). If no coverage data exists, say so.
- The 5 most-changed files in recent git history with NO test coverage (high-risk gaps).
- Skipped/pending/retry-flagged tests (flaky signals); test-to-code ratio outliers by module.
- Metric: test coverage percentage, untested-high-churn-file count.

### 6. API and interface consistency

Skip if the repo exposes no API/endpoints; note that in the residual.
- Endpoint naming, error-response format, and auth/authz patterns applied uniformly across endpoints.
- Metric: endpoint-convention-violation count.

## Report

After all analysis, synthesize one report. Tiers (DESIGN.md canonical):
- **Critical (this week)** — actively causing problems, or one bad merge from causing them.
- **Important (this month)** — will compound if left alone; debt accruing interest.
- **Track (next review)** — not urgent but trending the wrong way.

Each finding carries **location** (file/module) + **confidence** (Confirmed | Potential). This agent's addendum: a real accumulating problem is a finding, not a residual note; don't manufacture findings to fill tiers either.

Structure the report:

**Summary** — one paragraph: overall health, biggest concern, biggest strength.
**Critical**, **Important**, **Track** — findings grouped by tier.
**Metrics snapshot** — the numbers below. These key names are a **contract with `/deep-review`'s dashboard** (`commands/deep-review.md`) — do not rename them:

- Test coverage
- TODO/FIXME count
- Outdated deps
- Known vulnerabilities
- Largest file (lines)
- Coupling / circular-dependency count
- Dead-code symbol count
- Endpoint-convention-violation count

Mark any metric N/A (with the reason) when its lane was skipped.

**Trend vs last cycle** — if prior reports exist in `docs/studious/health-reviews/`, compare against the most recent and note each metric and finding as up/down/flat/new/resolved; else "baseline".
**Residual line** — what you verified clean, lanes skipped and why (stack detection), assumptions, and limitations.

Save the report to `docs/studious/health-reviews/YYYY-MM-DD-health-review.md`.
