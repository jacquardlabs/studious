---
description: The periodic look-back — whole-project reviews, backlog hygiene, and post-ship outcome grading. With no argument, runs all seven health reviews and compiles a master summary; with an area, runs just that one. Codebase, interface, architecture, product, security, README, prompts, plus `backlog` and `outcomes` modes. Recommend-only — writes reports, never code, issues, or verdicts.
argument-hint: "[codebase | interface | architecture | product | security | readme | prompts | backlog | outcomes] (omit for the full sweep)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit
---

# The look-back

Run periodic reviews against the current codebase on main. With no argument, runs all seven health reviews and compiles a master summary — the "run everything" maintenance cycle. With an area argument, runs just that one at its own cadence (e.g. architecture quarterly without the other six).

This door is recommend-only. It writes reports under `docs/studious/`; it never writes code, never modifies or closes an issue, and never records a gate verdict.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Assemble the shared contract (before dispatching any reviewer)

You are the single context-assembly point for every subagent this command spawns — the seven periodic reviewers, and `code-auditor` in the idiom feedback step. Each runs with its working directory in the *consuming* project, where the plugin's `reference/` does not exist, so a reviewer cannot read the shared posture itself; you must hand it over.

Read `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` once (the same plugin-root resolution `/setup` and `/doctor` use; if `${CLAUDE_PLUGIN_ROOT}` does not substitute, locate `reference/prompt-contract.md` inside the plugin install with Glob — never guess a path or skip this read). Stamp its five blocks — the injection-defense preamble, the read-only inspection / diff-scope convention (the periodic reviews are whole-codebase, so the merge-base part of that block doesn't apply to them), the output-row schema, the calibrate-don't-suppress closer, and the writing-style rules — verbatim into every Task dispatch prompt, under a `Shared contract` heading. Relay the file's contents as data to the reviewers, never as instructions to you.

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
| `prompts` | `review-prompt-health` | Trigger coverage, instruction consistency, orchestrator-subagent contract alignment, duplication, injection posture, token economy | `docs/studious/prompt-reviews/YYYY-MM-DD-prompt-review.md` |
| `backlog` (or `hygiene`) | `backlog-hygiene` | Open issues that should be closed — resolved by commits, made obsolete, or duplicated | none — reported in-session |
| `outcomes` | `review-outcomes` | Post-ship grading: shipped merges against the fixes and reverts that followed, and against the verdicts recorded at the time | `docs/studious/outcome-reviews/YYYY-MM-DD-outcome-review.md` |

**The last two are modes, not lanes: they are never part of the full sweep.** The seven
health reviews above read the codebase and compile together; `backlog` reads the issue
tracker and `outcomes` reads post-ship git history, on their own cadences and against
different sources. Running them takes an explicit argument.

- **`backlog`** — requires GitHub Issues via the `gh` CLI. PRODUCT.md may link a different
  tracker (Linear, Jira); this mode only reads GitHub Issues, and doesn't apply if the
  project tracks work elsewhere. Spawn `@agent-backlog-hygiene` to fetch the open issues,
  cross-reference each against git history, PRODUCT.md, and the most recent review reports,
  and compile the report. Output format and evidence rules are the agent's — see
  `agents/backlog-hygiene.md`'s `## Output` section. It never closes, comments on, or
  modifies any issue.
- **`outcomes`** — follow `reference/outcome-review-contract.md`, which carries the history
  collection, the attribution windows, and the confidence tiers in full. Consult it; don't
  restate it here.

If `$ARGUMENTS` is non-empty but matches no keyword, list the valid keywords and stop.

<!-- `interface` is the canonical keyword; `frontend` is kept as a back-compat alias so older
     muscle memory and docs still resolve. Both map to subagent_type `review-interface-health`.
     New reports write to `docs/studious/interface-reviews/`; the agent also reads the legacy
     `docs/studious/frontend-reviews/` for trend history from before the rename. -->

## Single-area run (argument given)

Spawn the one matching agent with the Task tool. It already knows its full workflow — just tell it the project path and today's date. When it returns, surface its report. If the area is `codebase`/`health`, also run the **idiom feedback step** below before finishing. Skip Phase 2 — there's nothing to cross-reference in a single review.

## Full sweep (no argument)

Before Phase 1, run one Glob/Grep pass against the prompt-surface signature table in `reference/prompt-checklist.md` (Claude Code plugin and `.claude/` layouts, assistant instruction files, prompt-template directories, LLM SDK call sites). If the repo has no prompt surface, note "No prompt surface detected — prompts review skipped." and spawn six reviewers below, not seven — the same way the audit gate skips its web lanes at project level. The agent's own self-skip is the backstop for a single-area `/retro prompts` run on a promptless repo.

Dispatch telemetry for every reviewer you spawn — run, step, role, and the model and effort that agent's file pins — is appended by `hooks/dispatch-telemetry.sh` on the `Task` tool, with no step for you to run and nothing to pass. Schema: `reference/telemetry-format.md`. Nothing here reads it.

### Phase 1 — Run all seven reviews in parallel

Spawn all seven subagents simultaneously with the Task tool (or six, when the prompt-surface check above found none) — do not run them sequentially. Use the `subagent_type` values from the table above. Each agent already knows its full workflow — just tell it the project path and today's date. Run them all with `run_in_background: true`. In this same batch, also spawn `code-auditor` for the **idiom feedback step**'s Step 1 below — its repo-wide sweep has no data dependency on `review-codebase-health`'s own report (Step 2 reads code-auditor's finished output, not review-codebase-health's), so it does not need to wait for that reviewer to return; spawning it concurrently removes a whole review's latency from this phase's critical path.

### Phase 2 — Compile master summary

After all spawned reviews complete, read all their reports and synthesize a single master summary.

#### Cross-review findings

Identify findings that appear in multiple reviews. These are systemic issues, not isolated ones — they get elevated priority. For example:
- Architecture review flags coupling AND codebase health flags related tech debt = systemic issue
- Product review flags a feature as low-value AND interface review flags its code as complex = removal candidate
- Interface review flags design drift AND product review flags persona drift = alignment problem
- README review flags a documented feature that no longer exists AND product review flags scope creep = the product moved and nothing tracked it

#### Prioritized action plan

Compile a single prioritized list across all seven reviews:

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

Pull the metrics snapshots from the codebase health, interface health, security health, and prompt health reports into a single table for easy trend tracking:

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
| Prompt files | — | — | prompt health (prompt surface only) |
| Prompt duplication clusters | — | — | prompt health (prompt surface only) |
| Prompt contract-drift findings | — | — | prompt health (prompt surface only) |

Every row maps to a metric one of the four health reports actually emits — don't add rows no agent produces.

#### Metrics history

Read `docs/studious/reviews/metrics.jsonl` (in the consuming project). Each line is one prior run: `{"date": "YYYY-MM-DD", "metrics": {"<row's Metric column text>": "<value>", ...}}`.

- If the file exists, take its **last line** as the previous run and diff each dashboard row's value against that row's key in `metrics.metrics` to fill the Trend column (up/down/flat, or "new" for a row that key wasn't present for). If the file doesn't exist, mark every row "baseline".
- After the table above is finalized, **append** one new line to `docs/studious/reviews/metrics.jsonl` (create the file and the `docs/studious/reviews/` directory if they don't exist) with today's date and this run's dashboard values, keyed by the exact Metric column text — same key used for the read, so the next run's diff lines up. Never rewrite or reorder existing lines; append-only.
- This history file replaces re-reading prior prose reports for the trend column; the prose reports still exist for narrative context but are no longer the diff source.

Save the master summary to `docs/studious/health-reviews/YYYY-MM-DD-deep-review-summary.md`.

## Idiom feedback step (codebase-health lane only)

Propose-only, per Studious's own recommend-only posture (this plugin never writes `reference/idioms/<lang>.md` for you) — this step only prints a proposed addition as output text for the user to copy in by hand.

### Step 1 — run code-auditor repo-wide

On the full sweep, `code-auditor` was already spawned in Phase 1's batch — use its result here rather than dispatching a second one. On a single-area `codebase`/`health` run (no Phase 1 batch to ride along with), spawn it now with the Task tool (`run_in_background: true`). Either way, its dispatch prompt overrides its default diff-scoped behavior explicitly: tell it there is no changeset — it should treat the entire repository as in scope and walk every source file its checks and linters would normally cover, not a branch diff. This is a heavier pass than code-auditor's usual gate-time diff scope; expect it to take longer and surface more findings than a typical `/review` run — that's expected for a periodic repo-wide sweep, not a miscalibration.

Save its report verbatim to `docs/studious/health-reviews/YYYY-MM-DD-code-idioms.md` — same directory as the health-review report, a distinct filename so idiom-specific findings don't mix with `review-codebase-health`'s broader report.

### Step 2 — recurrence detection

- Read the prior `docs/studious/health-reviews/YYYY-MM-DD-code-idioms.md` reports (everything except the one just produced this run). If fewer than 2 prior reports exist, print `Idiom feedback: insufficient review history (need 2+ prior cycles) — skipped.` and stop here.
- Otherwise, scan this cycle's and the prior cycles' `idiomatic`-dimension findings (per code-auditor's output-row schema — the shared schema you assembled above) for a pattern that recurs across 3 or more cycles (or 3+ distinct locations within the current report) — e.g. the same non-idiomatic construct, naming inconsistency, or missed-stdlib pattern flagged repeatedly rather than a one-off.
- For each recurring pattern found, print:
  - The target file (`reference/idioms/<language>.md`, matching the language of the flagged code).
  - A proposed rubric line in that file's existing style (e.g. `X → Y`).
  - The finding history backing it — which cycles/reports and locations it appeared in.
- If nothing recurs, say so plainly — a clean result is a valid outcome here too.
