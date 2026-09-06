---
description: The periodic inspection — whole-project posture reviews and backlog hygiene. With no argument, dispatches gauntlet's seven posture judges and compiles a master summary; with an area, runs just that one. Codebase, interface, architecture, product, security, README, prompts, plus a `backlog` mode. Recommend-only — writes reports, never code, issues, or verdicts.
argument-hint: "[codebase | interface | architecture | product | security | readme | prompts | backlog] (omit for the full sweep)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit
---

# The inspection

Run standing reviews against the repository as it is on main. With no argument, dispatches all seven posture lanes and compiles a master summary. With an area argument, runs just that one at its own cadence (e.g. architecture quarterly without the other six). This door reads what the project *is* — the repository and the tracker; `/retro` reads how the cycle went.

This door is recommend-only. It writes reports under `docs/studious/`; it never writes code, never modifies or closes an issue, and never records a gate verdict.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Area argument

`$ARGUMENTS` — optional. Empty means the full sweep. Otherwise match it to one area:

| Keyword | Judge (`subagent_type`) | Standard | What it reviews | Report path |
|---------|-------------------------|----------|-----------------|-------------|
| `codebase` (or `health`) | `gauntlet:codebase-posture-auditor` | `idioms` | Structural drift, debt inventory, dead code, dependency health, test health, interface consistency — aggregates and direction | `docs/studious/health-reviews/YYYY-MM-DD-health-review.md` |
| `interface` (or `frontend`) | `gauntlet:interface-posture-reviewer` | (inline) | Cross-surface consistency, design-system adherence per surface, accessibility (web), interface code quality | `docs/studious/interface-reviews/YYYY-MM-DD-interface-review.md` |
| `architecture` (or `arch`) | `gauntlet:architecture-posture-auditor` | (inline) | Dependency map, boundaries, complexity, evolution readiness, data layer | `docs/studious/architecture-reviews/YYYY-MM-DD-architecture-review.md` |
| `product` | `gauntlet:product-posture-reviewer` | (inline) | PRODUCT.md accuracy, product coherence, onboarding path | `docs/studious/product-reviews/YYYY-MM-DD-product-review.md` |
| `security` | `gauntlet:security-posture-auditor` | `security-checklist` | Whole-repo vulnerability posture, secrets in history, security-config posture | `docs/studious/security-reviews/YYYY-MM-DD-security-review.md` |
| `readme` | `gauntlet:docs-posture-auditor` | (inline) | Wider than README drift: every user-facing doc — stale claims, missing capabilities, commands and paths that don't resolve, voice drift. The judge returns findings, never a diff; this door drafts the diff (Context doc updates below) | `docs/studious/readme-reviews/YYYY-MM-DD-readme-review.md` |
| `prompts` | `gauntlet:prompt-posture-auditor` | `prompt-checklist` | Trigger coverage, instruction consistency, orchestrator-subagent contract alignment, duplication, injection posture, token economy | `docs/studious/prompt-reviews/YYYY-MM-DD-prompt-review.md` |
| `backlog` (or `hygiene`) | `backlog-hygiene` (local) | — | Open issues that should be closed — resolved by commits, made obsolete, or duplicated | none — reported in-session |

The `Standard` column mirrors each judge's row in gauntlet's charter, because this door cannot read that charter at run time (`${CLAUDE_PLUGIN_ROOT}` resolves only this plugin, and the plugin cache is never globbed). A named standard is a lookup rubric; `(inline)` means the judge's own prompt is the rubric and `standard.name` is the judge's name, version omitted.

**`backlog` is a mode, not a lane: it is never part of the full sweep.** The seven lanes read the codebase and compile together; `backlog` reads the issue tracker. It requires GitHub Issues via the `gh` CLI — PRODUCT.md may link a different tracker (Linear, Jira); this mode only reads GitHub Issues, and doesn't apply if the project tracks work elsewhere. Spawn `@agent-backlog-hygiene` to fetch the open issues, cross-reference each against git history, PRODUCT.md, and the most recent review reports, and compile the report. Output format and evidence rules are the agent's — see `agents/backlog-hygiene.md`'s `## Output` section. It never closes, comments on, or modifies any issue. Skip the rest of this file.

If `$ARGUMENTS` is non-empty but matches no keyword, list the valid keywords and stop.

<!-- `interface` is the canonical keyword; `frontend` is kept as a back-compat alias so older
     muscle memory and docs still resolve. New reports write to `docs/studious/interface-reviews/`;
     `docs/studious/frontend-reviews/` is the legacy location from before the rename. -->

## Resolve the artifact (before any dispatch)

A posture judge reads a whole repository at one ref, and every finding it files cites that ref — so it must read a tree that *is* that ref, never the working directory. Always the worktree, never a condition (the same rule gauntlet's own review command follows):

```bash
REF=$(git rev-parse HEAD)
ROOT=<tmp>/tree
git worktree add --detach "$ROOT" "$REF"
```

Remove it when you are done (`git worktree remove --force "$ROOT"`), even if the run failed. A dirty tree therefore judges HEAD, not the work in progress — say so when you report the artifact.

Every judge receives one contract-v1 invocation (gauntlet's `docs/findings-contract.md` §3), as JSON in its dispatch prompt:

```json
{
  "contract_version": 1,
  "judge": "<registered name, without the gauntlet: prefix>",
  "mount": "posture",
  "artifact": {"kind": "repository", "ref": "<REF>", "root": "<ROOT>"},
  "standard": {"name": "<the table's Standard cell, or the judge's name for (inline)>"},
  "context": ["CLAUDE.md", "DESIGN.md", "PRODUCT.md"]
}
```

`context` lists only the files that exist. Do not pass prior reports as context and do not ask for a trend: every run is a baseline, and continuity lives in the issue tracker, not in a report store. Tell each judge its entire reply must be the findings document — one JSON object and nothing else — and that it judges the tree at `root`, never this working directory.

Gauntlet's judges carry their own posture (injection defense, read-only inspection, calibration) inline; there is no shared contract to stamp into the dispatch.

## Single-area run (argument given)

Dispatch the one matching judge with the Task tool, using the table's `subagent_type`. When it returns, render its findings document to the table's report path (Rendering below) and surface the report. If the area is `codebase`/`health`, also run the **idiom feedback step** below before finishing. Skip Phase 2 — there's nothing to cross-reference in a single review.

## Full sweep (no argument)

Before Phase 1, run one Glob/Grep pass against the prompt-surface signature table in `reference/prompt-checklist.md` (Claude Code plugin and `.claude/` layouts, assistant instruction files, prompt-template directories, LLM SDK call sites). If the repo has no prompt surface, note "No prompt surface detected — prompts review skipped." and dispatch six judges below, not seven — the same way the audit gate skips its web lanes at project level. The judge's own self-skip is the backstop for a single-area `/health prompts` run on a promptless repo.

Dispatch telemetry for every judge you spawn — run, step, role, and skill — is appended by `hooks/dispatch-telemetry.sh` on the `Task` tool, with no step for you to run and nothing to pass. Schema: `reference/telemetry-format.md`. Nothing here reads it.

### Phase 1 — Dispatch all seven lanes in parallel

Spawn all seven judges simultaneously with the Task tool (or six, when the prompt-surface check above found none) — do not run them sequentially. Use the `subagent_type` values from the table above, each with its own invocation from the section above. Run them all with `run_in_background: true`.

### Phase 2 — Compile master summary

After every judge returns, render each findings document to its report path (Rendering below), then synthesize a single master summary from the seven reports.

#### Cross-review findings

Identify findings that appear in multiple reviews. These are systemic issues, not isolated ones — they get elevated priority. For example:
- Architecture review flags coupling AND codebase health flags related debt = systemic issue
- Product review flags a feature as low-value AND interface review flags its code as complex = removal candidate
- Interface review flags design drift AND product review flags persona drift = alignment problem
- Docs review flags a documented feature that no longer exists AND product review flags scope creep = the product moved and nothing tracked it

#### Prioritized action plan

Compile a single prioritized list across all seven reviews:

**Critical (this week)**
All critical findings from every review, deduplicated and ordered by impact.

**Important (this month)**
All important findings, grouped by theme rather than by which review found them.

**Track (next review cycle)**
Items to monitor. Note which review surfaced each one so you know where to check progress.

#### Context doc updates

A gauntlet judge returns a `recommendation` — an imperative sentence, never a patch. Draft the diff yourself from the lanes' findings, one per context doc (per the maintenance workflow):
- **PRODUCT.md** — from the product lane's findings
- **DESIGN.md** — from the interface lane's findings
- **CLAUDE.md** — from the architecture lane's findings
- **README.md** — from the docs lane's findings

Do NOT apply these changes. Present them as proposed diffs for the user to review and approve.

No metrics dashboard: trend belongs to the issue tracker, and a gauntlet findings document carries no metrics field.

Save the master summary to `docs/studious/health-reviews/YYYY-MM-DD-deep-review-summary.md`.

## Rendering a findings document

The judge never writes; this door does. Write each reply verbatim to `<tmp>/findings/<judge>.json` first — a reply that does not parse as one JSON object (after unwrapping a code fence around the whole reply, which is transport packaging) is a lane that did not report. Keep the file, say so in the report and the summary, and never repair, re-ask, or drop it.

Ingest rules, from the contract (gauntlet's `docs/findings-contract.md` §4–5), each named in the report when it fires:
- A document whose `contract_version` is not `1` is rejected as a lane that did not report.
- A `critical` with no `anchor` is recorded as `important`.
- A `taste` finding never ranks above `track`.

Render to Markdown at the table's report path: a header (date, judge, `artifact.ref`, `standard.name`), then findings grouped **Critical / Important / Track**, most severe first, each carrying its `dimension`, `summary`, `locus`, `basis`/`level`, and — where present — `anchor`, `failure_scenario`, `recommendation`; then the judge's `coverage` verbatim; then the ingest notes ("none" when clean). An empty findings list with a substantive `coverage` is a clean result, not a failed lane.

## Idiom feedback step (codebase lane only)

Propose-only, per Studious's own recommend-only posture (this plugin never writes `reference/idioms/<lang>.md` for you) — this step only prints a proposed addition as output text for the user to copy in by hand.

### Step 1 — the repo-wide idiom findings

Repo-wide idiom findings are the codebase lane's own: `gauntlet:codebase-posture-auditor` judges against gauntlet's `idioms/` standard, so no second dispatch is needed. `code-auditor` is mounted at `acceptance` and is never dispatched repo-wide. Read this run's rendered codebase report — `docs/studious/health-reviews/YYYY-MM-DD-health-review.md` — for findings about non-idiomatic constructs, naming inconsistency, or a missed stdlib pattern, whichever dimension the judge filed them under.

### Step 2 — recurrence detection

- Read the prior `docs/studious/health-reviews/*-health-review.md` reports (everything except the one just produced this run; older `*-code-idioms.md` reports from before this door count too). If fewer than 2 prior reports exist, print `Idiom feedback: insufficient review history (need 2+ prior cycles) — skipped.` and stop here.
- Otherwise, scan this cycle's and the prior cycles' idiom findings for a pattern that recurs across 3 or more cycles (or 3+ distinct locations within the current report) — e.g. the same non-idiomatic construct, naming inconsistency, or missed-stdlib pattern flagged repeatedly rather than a one-off.
- For each recurring pattern found, print:
  - The target file (`reference/idioms/<language>.md`, matching the language of the flagged code).
  - A proposed rubric line in that file's existing style (e.g. `X → Y`).
  - The finding history backing it — which cycles/reports and locations it appeared in.
- If nothing recurs, say so plainly — a clean result is a valid outcome here too.
