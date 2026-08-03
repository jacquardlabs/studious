---
description: Check tooling, plugin registration, and context-doc health for silent-degradation risks
allowed-tools: Read, Glob, Grep, Bash
---

# Studious doctor

A read-only health check for this Studious install, run in the consuming project. Gates and reviews assume tools, a registered agent/skill roster, and populated context docs are all present — when one is missing, nothing errors, it just quietly has less to work with. This command surfaces those gaps in one pass. It fixes nothing: recommend-only, same as every gate and review. It is not a gate — no verdict token, nothing recorded to `.studious/`.

## 1. Tooling

Run each check and classify the result:

- **Git repo** — run `git rev-parse --is-inside-work-tree`. If it fails: **Critical** — "not a git repo: gate ledger, merge-base diffing, and every gate that scopes to 'this branch' cannot function."
- **`jq` present** — run `command -v jq`. If it fails: **Critical** — "jq missing: `gate-ledger record` silently no-ops (see `bin/gate-ledger`'s own comment: 'Degrades silently when git or jq is unavailable') — no gate verdict, and no `/next` flow position, will ever be recorded."
- **`gh` authenticated** — run `gh auth status`. If `gh` itself is missing, or the command exits non-zero: **Important** — "gh missing or unauthenticated: `/bet`, `/retro`, and the PR-time gate reminder's context all depend on it."
- **`python3` present** — run `command -v python3`. If it fails: **Critical** — "python3 missing: every build script (`plan-lint`, `design-lint`, `verify`, `status-flip`, `evidence-capture`, `evidence-freshness`, `build-report`, `worktree-setup`) is a Python CLI, so `/build` cannot lint a plan and `/build` cannot verify a single task — it would report success off nothing but the executor's own claim."
- **`viva` available** — the plugin manifest's only declared dependency. Check the way `skills/shape/SKILL.md` already reasons about it: look for the `viva` skill in this session's registered skill listing. If absent: **Critical** — "viva missing: `/shape` and `/build` both end in a human sign-off round they cannot run, so neither completes."

Report each check as **OK** when it succeeds. These five are the tools; the first three are gate-side, the last two are build-side — a Studious install missing either half degrades silently in exactly the way this command exists to catch.

## 2. Plugin health

Every agent and skill Studious ships must actually be registered this session — a file present on disk with malformed frontmatter fails to register but leaves no error, silently dropping a `/review` lane or a natural-language trigger.

1. Locate the plugin's own shipped roster: glob `${CLAUDE_PLUGIN_ROOT}/agents/*.md` for agent names (filename minus `.md`) and `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` for skill names (parent directory name). If `${CLAUDE_PLUGIN_ROOT}` doesn't resolve, locate the plugin's own `agents/` and `skills/` directories with Glob instead (same fallback `/setup` uses for templates) — don't guess a path.
2. Compare that shipped roster against what this session actually has registered: the agent names available to the Agent tool and the skill names available to the Skill tool, both already present in your own system context for this conversation (the "Available agent types" and available-skills listings injected at session start). Do not re-derive this list by reading files a second time — the whole point is to check what got registered, not what's on disk. If that system-context listing itself isn't present or isn't clearly readable this session (its format is a Claude Code internal, not a stable contract this command controls), do not guess — report plugin health as **Inconclusive**: "could not read this session's registered agent/skill listing — re-run in a session where it's present" rather than emitting a false Critical.
3. Any shipped agent or skill absent from the session's registered list is **Critical** — name it and state the consequence: "`<name>` shipped but not registered this session — `/review` (or the matching gate) silently runs without this lane."
4. Report the roster size as counts derived from step 1 (e.g. "15 agents, 4 skills shipped") — never hardcode a count.

If everything shipped is registered, report **OK** with the counts.

## 3. Context docs

For each of PRODUCT.md, DESIGN.md, CLAUDE.md in the consuming project's root:

- **Missing** — the file doesn't exist. **Important** — "gates and reviews that read this file have no project context."
- **Stub** — the file exists, but for PRODUCT.md/DESIGN.md, compare its section content against the placeholder comments shipped at `${CLAUDE_PLUGIN_ROOT}/templates/PRODUCT.md` / `${CLAUDE_PLUGIN_ROOT}/templates/DESIGN.md` (same plugin-root resolution and Glob fallback as section 2). Two classes of template heading are exempt from this check, since the template itself marks them optional: any heading whose text contains `(if applicable)` (e.g. PRODUCT.md's "Secondary persona (if applicable)"), and DESIGN.md's `## Per-surface conventions` subsections except whichever match a surface actually listed in the doc's own `## Surfaces` table — the template's own instructions say to delete the rest, so their absence or placeholder state isn't a stub signal. The `## Surfaces` table records fixed machine tokens, not headings, so translate with this exact mapping: `web` → `### Web`, `cli` → `### CLI`, `plugin` → `### Plugin / prompt tooling`, `tui` → `### TUI`, `api` → `### API`, `report` → `### Report / export`; `library` has no matching subsection at all (a pure library keeps this doc minimal per the template's own instruction). If **any** other required section (each remaining `##`/`###` heading in the template) still contains only its template's placeholder comment rather than replaced prose, classify the whole doc as stub — a partially-filled doc is exactly the half-false-confidence state this check exists to catch. Report as **Important** — "`<doc>` is still the shipped template (`<section>` unedited) — gates read it but get no real project context." A doc that also carries its own `<!-- FILL IN: ... -->` author TODOs on top of real prose is **not** a stub on that basis alone — that's a populated doc with open follow-ups, not the original scaffold.
- **Populated** — anything else. Report **OK**.

CLAUDE.md has no shipped template (`templates/CLAUDE.md` does not exist), so it only ever reports **missing** or **populated** — never stub.

## 4. Flow-state hygiene

`.studious/` accumulates one work file per feature and one state file per epic, and nothing collects them automatically. When they pile up, `/next` with no argument stops being able to answer "what's next" — it has to ask you to pick from a list instead (#237).

`gate-ledger work-list` (one line per work file: slug, phase, branch, title) gives the raw inventory; classify each line by phase, matching `commands/next.md`'s own definition:

- **Active** — phase not `done`/`stopped`. This is the count that governs `/next`'s no-argument menu (`commands/next.md`'s resolve-the-feature step lists exactly the active work files) — it's the number that answers "will `/next` have to ask me to choose?"
- **Retained** — phase `done`/`stopped`, and `gate-ledger work-get --slug <slug>` (never a raw file read — work files are read and written only through the ledger tool, same as `commands/next.md`'s own rule) shows at least one *measured* `scopeDelta` entry (#244), i.e. one with `unmeasured` not `true`. `gate-ledger gc` keeps such a file until its retention window lapses — `bin/gate-ledger`'s `SCOPE_DELTA_RETENTION_DAYS`, checked against the file's last write, not when its flow ended — after which plain `gc` collects it too; `gate-ledger gc --force` collects it immediately regardless. A work file whose scope-delta cohort is entirely `unmeasured` carries none of this protection and collects on the very next plain `gc`.

Also count epic state by globbing `.studious/epics/*.json`.

Classify:

- **More than 10 active work files** — **Important** — "`/next` will ask you to choose from N features instead of resuming one." Retained files never appear in that menu — they're terminal-phase — so they don't count toward this threshold on their own, but if any exist, name them too: "`gate-ledger work-get --slug <slug>` reads any of them before they go; `gate-ledger gc --force` collects M retained now, discarding each one's measured scope-delta history for good; plain `gate-ledger gc` collects whichever have already passed their `SCOPE_DELTA_RETENTION_DAYS` window (same permanent loss), and the rest once it passes."
- **1–10 active** — **OK**, with the active count (and the retained count, if nonzero).
- **A work file whose branch no longer exists** — name it: `gc` will collect it outright on its next run, no retention window and no `--force` needed even if it carries a measured scope-delta cohort — that guard applies to a *finished* story's work file only, never to a still-in-flight one whose branch is gone (a parked story never reached acceptance, so there is no completed cohort to protect) — and until collected it is noise in every `work-list` read.

Report the counts, never the full list — this is a health check, not an inventory. And recommend `gc`; never run it. Same recommend-only posture as every other check in this command.

## 5. Retired door names

The door surface collapsed from eighteen names to nine (`reference/personas.md`). A
consuming project's `CLAUDE.md`, its README, or a `.github/` workflow may still name a
door that no longer exists — an instruction pointing at nothing, which reads as Studious
being broken rather than as a stale reference.

Read `reference/personas.md`'s `Absorbed` column: each row lists the names that door took
over. Grep the consuming project's `CLAUDE.md`, `README.md`, and `.github/workflows/*.yml`
for any of them as a slash-command invocation (`/work-on`, not `docs/design/`), and report
each hit with the door that replaced it.

**Propose, don't apply.** Print the rewire as a diff the human can apply; never edit their
files. This is the same posture every other check here takes — `/doctor` fixes nothing.

Absent files are not findings: a project without a README simply has nothing to check.

## Output

```
## Studious doctor

**Tooling**
- [OK|Important|Critical] <check>: <status, and consequence if not OK>

**Plugin health**
- [OK|Critical|Inconclusive] <n agents, m skills shipped and registered | list of unregistered names with consequence | reason session roster couldn't be read>

**Context docs**
- [OK|Important] PRODUCT.md: <populated | stub (<section>) | missing> — <consequence if not OK>
- [OK|Important] DESIGN.md: <same>
- [OK|Important] CLAUDE.md: <populated | missing> — <consequence if not OK>

**Retired door names**
- [OK|Important] <no retired door names found | `<file>:<line>` names `/<old>`, now `/<new>`> — <consequence if not OK>

**Flow state**
- [OK|Important] <n active, k retained for scope-delta, m epics> — <"clean" | "`/next` will ask you to choose from n features" | "k retained for scope-delta — `gate-ledger work-get --slug <slug>` to read any before deciding; `gate-ledger gc --force` to collect now (discards their scope-delta history for good), or plain `gc` once their window lapses (same permanent loss)">

### Summary
<N> critical, <N> important, <N> ok. This is a health check, not a gate — no verdict token, nothing recorded to the ledger.
```

Findings use the same severity vocabulary as every other Studious command (`Critical` · `Important` · `Track` — see `reference/severity-rubric.md`); nothing in this command reaches `Track`, since every check here is binary (a tool either silently breaks something or it doesn't).
