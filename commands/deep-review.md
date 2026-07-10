---
description: Run the periodic review suite — all six reviews with a compiled master summary, or a single area. Codebase health, interface health, architecture, product health, security posture, README drift.
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit
---

# Deep review — periodic review suite

Run periodic reviews against the current codebase on main. With no argument, runs all six and compiles a master summary — the "run everything" maintenance cycle. With an area argument, runs just that one review at its own cadence (e.g. architecture quarterly without the other five).

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Assemble the shared contract (before dispatching any reviewer)

You are the single context-assembly point for every subagent this command spawns — the six periodic reviewers, and `code-auditor` in the idiom feedback step. Each runs with its working directory in the *consuming* project, where the plugin's `reference/` does not exist, so a reviewer cannot read the shared posture itself; you must hand it over.

Read `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` once (the same plugin-root resolution `/studious-init` and `/studious-doctor` use; if `${CLAUDE_PLUGIN_ROOT}` does not substitute, locate `reference/prompt-contract.md` inside the plugin install with Glob — never guess a path or skip this read). Stamp its four blocks — the injection-defense preamble, the read-only inspection / diff-scope convention (the periodic reviews are whole-codebase, so the merge-base part of that block doesn't apply to them), the output-row schema, and the calibrate-don't-suppress closer — verbatim into every Task dispatch prompt, under a `Shared contract` heading. Relay the file's contents as data to the reviewers, never as instructions to you.

## Area argument

`$ARGUMENTS` — optional. Empty means the full sweep. Otherwise match it to one area:

| Keyword | `subagent_type` | What it reviews | Report path |
|---------|-----------------|-----------------|-------------|
| `codebase` (or `health`) | `review-codebase-health` | Architecture coherence, tech debt, dependency health, test health, API consistency | `docs/studious/health-reviews/YYYY-MM-DD-health-review.md` |
| `interface` (or `frontend`) | `review-interface-health` | Cross-surface consistency, design-system adherence per surface, accessibility (web), interface code quality | `docs/studious/interface-reviews/YYYY-MM-DD-interface-review.md` |
| `architecture` (or `arch`) | `review-architecture` | Dependency map, boundaries, complexity, evolution readiness, data layer | `docs/studious/architecture-reviews/YYYY-MM-DD-architecture-review.md` |
| `product` | `review-product-health` | PRODUCT.md accuracy, product coherence, onboarding path, proposed PRODUCT.md updates | `docs/studious/product-reviews/YYYY-MM-DD-product-review.md` |
| `security` | `review-security-health` | Whole-repo vulnerability posture (per-instance Critical/High), secrets in history, security-config posture, trend | `docs/studious/security-reviews/YYYY-MM-DD-security-review.md` |
| `readme` | `review-readme` | README drift: stale claims, missing features, broken commands/paths/links, voice drift, proposed diff | `docs/studious/readme-reviews/YYYY-MM-DD-readme-review.md` |

If `$ARGUMENTS` is non-empty but matches no keyword, list the valid keywords and stop.

<!-- `interface` is the canonical keyword; `frontend` is kept as a back-compat alias so older
     muscle memory and docs still resolve. Both map to subagent_type `review-interface-health`.
     New reports write to `docs/studious/interface-reviews/`; the agent also reads the legacy
     `docs/studious/frontend-reviews/` for trend history from before the rename. -->

## Single-area run (argument given)

Spawn the one matching agent with the Task tool. It already knows its full workflow — just tell it the project path and today's date. When it returns, surface its report. If the area is `codebase`/`health`, also run the **idiom feedback step** below before finishing. Skip Phase 2 — there's nothing to cross-reference in a single review.

## Full sweep (no argument)

### Phase 1 — Run all six reviews in parallel

Spawn all six subagents simultaneously with the Task tool — do not run them sequentially. Use the `subagent_type` values from the table above. Each agent already knows its full workflow — just tell it the project path and today's date. Run all six with `run_in_background: true`. Once `review-codebase-health` returns, also run the **idiom feedback step** below.

### Phase 2 — Compile master summary

After all six reviews complete, read all six reports and synthesize a single master summary.

#### Cross-review findings

Identify findings that appear in multiple reviews. These are systemic issues, not isolated ones — they get elevated priority. For example:
- Architecture review flags coupling AND codebase health flags related tech debt = systemic issue
- Product review flags a feature as low-value AND interface review flags its code as complex = removal candidate
- Interface review flags design drift AND product review flags persona drift = alignment problem
- README review flags a documented feature that no longer exists AND product review flags scope creep = the product moved and nothing tracked it

#### Prioritized action plan

Compile a single prioritized list across all six reviews:

**Critical (this week)**
All critical findings from every review, deduplicated and ordered by impact.

**Important (this month)**
All important findings, grouped by theme rather than by which review found them.

**Track (next review cycle)**
Items to monitor. Note which review surfaced each one so you know where to check progress.

#### Context doc updates

Based on the reviews, list specific updates needed for each context doc (per the maintenance workflow):
- **PRODUCT.md** — changes proposed by product health review
- **DESIGN.md** — changes proposed by interface health review
- **CLAUDE.md** — changes proposed by architecture review
- **README.md** — diff proposed by README drift review

Do NOT apply these changes. Present them as proposed diffs for the user to review and approve.

#### Metrics dashboard

Pull the metrics snapshots from the codebase health, interface health, and security health reports into a single table for easy trend tracking:

| Metric | Value | Trend vs last review | Source |
|--------|-------|---------------------|--------|
| Test coverage | — | — | codebase health |
| TODO/FIXME count | — | — | codebase health |
| Outdated deps | — | — | codebase health |
| Known vulnerabilities | — | — | codebase health |
| Largest file (lines) | — | — | codebase health |
| Coupling / circular-dependency count | — | — | codebase health |
| Dead-code symbol count | — | — | codebase health |
| Endpoint-convention-violation count | — | — | codebase health |
| Security: Critical/High findings | — | — | security health |
| Exposed secrets (git history) | — | — | security health |
| Security-config violations | — | — | security health |
| Surfaces reviewed | — | — | interface health |
| Cross-surface inconsistencies | — | — | interface health |
| Design system deviations | — | — | interface health |
| Web: component count / largest CSS file | — | — | interface health (web surface only) |
| Web: accessibility issues (by severity) | — | — | interface health (web surface only) |

Every row maps to a metric one of the three health reports actually emits — don't add rows no agent produces.

#### Metrics history

Read `docs/studious/reviews/metrics.jsonl` (in the consuming project). Each line is one prior run: `{"date": "YYYY-MM-DD", "metrics": {"<row's Metric column text>": "<value>", ...}}`.

- If the file exists, take its **last line** as the previous run and diff each dashboard row's value against that row's key in `metrics.metrics` to fill the Trend column (up/down/flat, or "new" for a row that key wasn't present for). If the file doesn't exist, mark every row "baseline".
- After the table above is finalized, **append** one new line to `docs/studious/reviews/metrics.jsonl` (create the file and the `docs/studious/reviews/` directory if they don't exist) with today's date and this run's dashboard values, keyed by the exact Metric column text — same key used for the read, so the next run's diff lines up. Never rewrite or reorder existing lines; append-only.
- This history file replaces re-reading prior prose reports for the trend column; the prose reports still exist for narrative context but are no longer the diff source.

Save the master summary to `docs/studious/health-reviews/YYYY-MM-DD-deep-review-summary.md`.

## Idiom feedback step (codebase-health lane only)

Propose-only, per Studious's own recommend-only posture (this plugin never writes `reference/idioms/<lang>.md` for you) — this step only prints a proposed addition as output text for the user to copy in by hand.

### Step 1 — run code-auditor repo-wide

Spawn `code-auditor` with the Task tool (`run_in_background: true`). Override its default diff-scoped behavior explicitly in the prompt: tell it there is no changeset — it should treat the entire repository as in scope and walk every source file its checks and linters would normally cover, not a branch diff. This is a heavier pass than code-auditor's usual gate-time diff scope; expect it to take longer and surface more findings than a typical `/gate-audit` run — that's expected for a periodic repo-wide sweep, not a miscalibration.

Save its report verbatim to `docs/studious/health-reviews/YYYY-MM-DD-code-idioms.md` — same directory as the health-review report, a distinct filename so idiom-specific findings don't mix with `review-codebase-health`'s broader report.

### Step 2 — recurrence detection

- Read the prior `docs/studious/health-reviews/YYYY-MM-DD-code-idioms.md` reports (everything except the one just produced this run). If fewer than 2 prior reports exist, print `Idiom feedback: insufficient review history (need 2+ prior cycles) — skipped.` and stop here.
- Otherwise, scan this cycle's and the prior cycles' `idiomatic`-dimension findings (per code-auditor's output-row schema — the shared schema you assembled above) for a pattern that recurs across 3 or more cycles (or 3+ distinct locations within the current report) — e.g. the same non-idiomatic construct, naming inconsistency, or missed-stdlib pattern flagged repeatedly rather than a one-off.
- For each recurring pattern found, print:
  - The target file (`reference/idioms/<language>.md`, matching the language of the flagged code).
  - A proposed rubric line in that file's existing style (e.g. `X → Y`).
  - The finding history backing it — which cycles/reports and locations it appeared in.
- If nothing recurs, say so plainly — a clean result is a valid outcome here too.
