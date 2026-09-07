---
description: The periodic inspection — whole-project posture reviews and backlog hygiene. With no argument, dispatches gauntlet's seven posture judges and compiles a master summary; with an area, runs just that one. Codebase, interface, architecture, product, security, README, prompts, plus `backlog` and `simplify` modes. Recommend-only — writes reports, never code, issues, or verdicts.
argument-hint: "[codebase | interface | architecture | product | security | readme | prompts | backlog | simplify] (omit for the full sweep)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit, Skill
---

# The inspection

Run standing reviews against the repository as it is on main. With no argument, dispatches all seven posture lanes and compiles a master summary. With an area argument, runs just that one at its own cadence (e.g. architecture quarterly without the other six). This door reads what the project *is* — the repository and the tracker; `/retro` reads how the cycle went.

This door is recommend-only. It writes reports under `docs/studious/` (`simplify` leaves exorcist's register under `docs/exorcist/`, that plugin's own convention); it never writes code, never modifies or closes an issue, and never records a gate verdict.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Area argument

`$ARGUMENTS` — optional. Empty means the full sweep. Otherwise match it to one area:

| Keyword | Judge (`subagent_type`) | What it reviews | Report path |
|---------|-------------------------|-----------------|-------------|
| `codebase` (or `health`) | `gauntlet:codebase-posture-auditor` | Structural drift, debt inventory, dead code, dependency health, test health, interface consistency — aggregates and direction | `docs/studious/health-reviews/YYYY-MM-DD-health-review.md` |
| `interface` (or `frontend`) | `gauntlet:interface-posture-reviewer` | Cross-surface consistency, design-system adherence per surface, accessibility (web), interface code quality | `docs/studious/interface-reviews/YYYY-MM-DD-interface-review.md` |
| `architecture` (or `arch`) | `gauntlet:architecture-posture-auditor` | Dependency map, boundaries, complexity, evolution readiness, data layer | `docs/studious/architecture-reviews/YYYY-MM-DD-architecture-review.md` |
| `product` | `gauntlet:product-posture-reviewer` | PRODUCT.md accuracy, product coherence, onboarding path | `docs/studious/product-reviews/YYYY-MM-DD-product-review.md` |
| `security` | `gauntlet:security-posture-auditor` | Whole-repo vulnerability posture, secrets in history, security-config posture | `docs/studious/security-reviews/YYYY-MM-DD-security-review.md` |
| `readme` | `gauntlet:docs-posture-auditor` | Wider than README drift: every user-facing doc — stale claims, missing capabilities, commands and paths that don't resolve, voice drift. The judge returns findings, never a diff; this door drafts the diff (Context doc updates below) | `docs/studious/readme-reviews/YYYY-MM-DD-readme-review.md` |
| `prompts` | `gauntlet:prompt-posture-auditor` | Trigger coverage, instruction consistency, orchestrator-subagent contract alignment, duplication, injection posture, token economy | `docs/studious/prompt-reviews/YYYY-MM-DD-prompt-review.md` |
| `backlog` (or `hygiene`) | `backlog-hygiene` (local) | Open issues that should be closed — resolved by commits, made obsolete, or duplicated | none — reported in-session |
| `simplify` (or `seance`) | `/exorcist:seance` (skill, not a dispatch) | Standing simplification targets — pattern contention, dead code, duplicated helpers, wrapper strata — as a ranked register. Working it is the human's act: `/bet` the register or `/exorcist:exorcise <dir>/register.json`; this door never applies one | `docs/exorcist/seance-YYYY-MM-DD/register.json` (exorcist writes it; `register.md` is its rendering) |

**`backlog` is a mode, not a lane: it is never part of the full sweep.** The seven lanes read the codebase and compile together; `backlog` reads the issue tracker. It requires GitHub Issues via the `gh` CLI — PRODUCT.md may link a different tracker (Linear, Jira); this mode only reads GitHub Issues, and doesn't apply if the project tracks work elsewhere. Spawn `@agent-backlog-hygiene` to fetch the open issues, cross-reference each against git history, PRODUCT.md, and the most recent review reports, and compile the report. Output format and evidence rules are the agent's — see `agents/backlog-hygiene.md`'s `## Output` section. It never closes, comments on, or modifies any issue. Skip the rest of this file.

**`simplify` is the other mode, opt-in for the same reason `backlog` is:** the séance's four lanes read the whole tree at opus — ~75 minutes on a 20k-line repository (exorcist's README, Cost) — so it never rides the bare sweep. Check whether exorcist is installed the way `/setup` Step 6b does: look for `exorcist:seance` in this session's registered skill listing — never a file path.

- **Not installed:** one line — "exorcist not installed — simplify skipped; install with `/plugin install exorcist@jacquardlabs-marketplace`." — and stop. Never an error: the mode is optional.
- **Installed:** invoke `/exorcist:seance` (it surveys HEAD) and relay its report verbatim. It resolves its own worktree and writes only under `docs/exorcist/seance-<date>/`; nothing in the tree changes. Point at `register.json` and stop: setting ghosts `approved` there and working them — `/bet` the register or `/exorcist:exorcise <dir>/register.json` — is a human-typed producer act, never this door's.

Either way, skip the rest of this file.

If `$ARGUMENTS` is non-empty but matches no keyword, list the valid keywords and stop.

<!-- `interface` is the canonical keyword; `frontend` is kept as a back-compat alias so older
     muscle memory and docs still resolve. New reports write to `docs/studious/interface-reviews/`;
     `docs/studious/frontend-reviews/` is the legacy location from before the rename. -->

## Locate gauntlet (before any dispatch)

Every posture lane is a `gauntlet:<judge>` dispatch — gauntlet is the fleet, this door is a consumer. Two scripts in gauntlet's plugin root drive it: `scripts/dispatch.py` builds one validated contract-v1 invocation per judge (gauntlet's `docs/findings-contract.md` §3) and resolves each judge's standard from gauntlet's own charter, and `scripts/report.py` compiles the findings documents the judges return (§4). Nothing here restates that contract — each invocation is handed to its judge verbatim, and this door only decides *which* invocations run. The judges carry their own posture (injection defense, read-only inspection, calibration).

**Gauntlet's root.** `${CLAUDE_PLUGIN_ROOT}` resolves to this plugin's root, never gauntlet's. Once per session, in this order: invoke the `gauntlet:where` skill if it is in this session's skill listing — its first line is gauntlet's absolute root; else invoke `gauntlet:review` with `--help` as its argument — it stops before any dispatch, and the loaded text carries the root in its `python3 "…/scripts/dispatch.py"` lines (gauntlet 0.15.0 ships no `where`). Record it as `GAUNTLET_ROOT` for the rest of the session (`commands/review.md`, "Locate gauntlet", says why these are the two honest routes). If neither is in the listing, gauntlet is not installed: stop with one line — "gauntlet is not installed — `/plugin install gauntlet@jacquardlabs-marketplace`, then re-run" — never a guess. **Never Glob the plugin cache** for it.

## Resolve the artifact (before any dispatch)

A posture judge reads a whole repository at one ref, and every finding it files cites that ref — so it must read a tree that *is* that ref, never the working directory. Always the worktree, never a condition (the same rule gauntlet's own review command follows; `dispatch.py` refuses a tree that is not the ref):

```bash
scratch=$(mktemp -d "${TMPDIR:-/tmp}/studious-health.XXXXXX") && mkdir "$scratch/findings"
REF=$(git rev-parse HEAD)
git worktree add --detach "$scratch/tree" "$REF"
git ls-tree -r --name-only "$REF" > "$scratch/paths.txt"
python3 "$GAUNTLET_ROOT/scripts/dispatch.py" \
  --ref "$REF" --root "$scratch/tree" --paths "$scratch/paths.txt" \
  --context "<context files>" > "$scratch/invocations.json"
```

`<context files>` is the comma-separated subset of `CLAUDE.md,DESIGN.md,PRODUCT.md` that exists. Do not pass prior reports as context and do not ask for a trend: every run is a baseline, and continuity lives in the issue tracker, not in a report store. If `dispatch.py` exits non-zero, relay its stderr — a refused tree or an empty selection is the answer, not an error to route around. Remove the worktree (`git worktree remove --force "$scratch/tree"`) and the scratch directory when the run ends, even if it failed. A dirty tree therefore judges HEAD, not the work in progress — say so when you report the artifact.

**Filter to the run's lanes.** `dispatch.py` emits every `posture` judge; keep only the ones this run dispatches — the table's one judge for a single-area run, all seven for the sweep (six when the prompt-surface check below found none). Write that list as a JSON array of judge names and keep the matching invocations:

```bash
jq --argjson keep '["codebase-posture-auditor",...]' \
  '[.[] | select(.judge as $j | $keep | index($j))]' "$scratch/invocations.json" > "$scratch/round.json"
```

**Dispatch.** One `Task` per invocation in `round.json`, all in a single message, in parallel — `subagent_type` is `gauntlet:<judge>`, and the prompt is that judge's invocation object, verbatim, followed by "your entire reply must be the findings document — one JSON object and nothing else" and "judge the tree at `artifact.root`, never this working directory". Prose rides *beside* the invocation, never inside it. Write each reply verbatim to `$scratch/findings/<judge>.json`; a reply that does not parse is a lane that did not report — keep the file as it came back, never repair or re-ask, and let `report.py` say so.

## Single-area run (argument given)

Dispatch the one matching judge (the `$keep` list is that one name). When it returns, compile (below) and write the compiled report to the table's report path, then surface it. Skip Phase 2 — there's nothing to cross-reference in a single review. The idiom-rubric proposal that used to follow the codebase lane is `/retro`'s (section 4) — it reads the reports this door writes.

## Full sweep (no argument)

Before Phase 1, run one Glob/Grep pass against the prompt-surface signature table in `reference/prompt-checklist.md` (Claude Code plugin and `.claude/` layouts, assistant instruction files, prompt-template directories, LLM SDK call sites). If the repo has no prompt surface, note "No prompt surface detected — prompts review skipped." and dispatch six judges below, not seven — the same way the audit gate skips its web lanes at project level. The judge's own self-skip is the backstop for a single-area `/health prompts` run on a promptless repo.

Dispatch telemetry for every judge you spawn — run, step, role, and skill — is appended by `hooks/dispatch-telemetry.sh` on the `Task` tool, with no step for you to run and nothing to pass. Schema: `reference/telemetry-format.md`. Nothing here reads it.

### Phase 1 — Dispatch all seven lanes in parallel

Spawn all seven judges simultaneously (or six, when the prompt-surface check above found none) — do not run them sequentially. `$keep` is every judge in the table, minus `prompt-posture-auditor` when skipped; each dispatch is its own invocation from `round.json`, per the Dispatch step above. Run them all with `run_in_background: true`.

### Phase 2 — Compile master summary

After every judge returns, compile (below): one `report.py` run per lane writes each area's report at the table's path, and one run over the whole findings directory is the sweep's compiled report. Synthesize the master summary from the seven area reports and that compiled report — a finding `report.py` merged across lanes (its attribution names more than one judge) is a cross-review finding by construction.

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

If a séance register exists (`docs/exorcist/seance-*/register.json`; `register.md` is its rendering), link the newest under the action plan — it is a lead for the human, never a lane in this sweep.

Save the master summary to `docs/studious/health-reviews/YYYY-MM-DD-deep-review-summary.md`.

## Compile the findings

Run gauntlet's compiler over the run's findings directory, expecting exactly the judges this run dispatched:

```bash
python3 "$GAUNTLET_ROOT/scripts/report.py" --findings "$scratch/findings" \
  --expect "$(jq -r '[.[].judge] | join(",")' "$scratch/round.json")"
```

It validates every document at the boundary, applies the contract's ingest rules (anchor-or-demote, taste-caps-at-track), names every demotion and unwrap, and renders the findings most-severe-first with each judge's `coverage`; a non-zero exit means at least one expected lane did not report — say so in the report and the summary, never drop the lane. An empty findings list with a substantive `coverage` is a clean result, not a failed lane. It prints no verdict, by design — this door records none either.

The area report files are `report.py`'s markdown, one run per lane — `report.py` reads one flat directory and merges findings across the judges in it, so a per-lane directory is simpler than splitting a merged report by judge. On a single-area run the compiled run above *is* the area report. On the sweep:

```bash
for judge in $(jq -r '.[].judge' "$scratch/round.json"); do
  mkdir -p "$scratch/lane/$judge" && cp "$scratch/findings/$judge.json" "$scratch/lane/$judge/" 2>/dev/null
  python3 "$GAUNTLET_ROOT/scripts/report.py" --findings "$scratch/lane/$judge" --expect "$judge" > <that judge's report path>
done
```

A lane that never wrote a document still renders — as a report whose only content is that the judge did not report.
