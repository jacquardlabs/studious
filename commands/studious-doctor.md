---
description: Check tooling, plugin registration, and context-doc health for silent-degradation risks
allowed-tools: Read, Glob, Grep, Bash
---

# Studious doctor

A read-only health check for this Studious install, run in the consuming project. Gates and reviews assume tools, a registered agent/skill roster, and populated context docs are all present — when one is missing, nothing errors, it just quietly has less to work with. This command surfaces those gaps in one pass. It fixes nothing: recommend-only, same as every other Studious command. It is not a gate — no verdict token, nothing recorded to `.studious/`.

## 1. Tooling

Run each check and classify the result:

- **Git repo** — run `git rev-parse --is-inside-work-tree`. If it fails: **Critical** — "not a git repo: gate ledger, merge-base diffing, and every gate that scopes to 'this branch' cannot function."
- **`jq` present** — run `command -v jq`. If it fails: **Critical** — "jq missing: `gate-ledger record` silently no-ops (see `bin/gate-ledger`'s own comment: 'Degrades silently when git or jq is unavailable') — no gate verdict, and no `/work-on` flow position, will ever be recorded."
- **`gh` authenticated** — run `gh auth status`. If `gh` itself is missing, or the command exits non-zero: **Important** — "gh missing or unauthenticated: `/backlog-priorities`, `/backlog-hygiene`, and the PR-time gate reminder's context all depend on it."
- **`python3` present** — run `command -v python3`. If it fails: **Critical** — "python3 missing: every build script (`plan-lint`, `design-lint`, `verify`, `status-flip`, `evidence-capture`, `evidence-freshness`, `build-report`, `worktree-setup`) is a Python CLI, so `/plan` cannot lint a plan and `/build` cannot verify a single task — it would report success off nothing but the executor's own claim."
- **`viva` available** — the plugin manifest's only declared dependency. Check the way `skills/design/SKILL.md` already reasons about it: look for the `viva` skill in this session's registered skill listing. If absent: **Critical** — "viva missing: `/design` and `/plan` both end in a human sign-off round they cannot run, so neither completes."

Report each check as **OK** when it succeeds. These five are the tools; the first three are gate-side, the last two are build-side — a Studious install missing either half degrades silently in exactly the way this command exists to catch.

## 2. Plugin health

Every agent and skill Studious ships must actually be registered this session — a file present on disk with malformed frontmatter fails to register but leaves no error, silently dropping a `/gate-audit` lane or a natural-language trigger.

1. Locate the plugin's own shipped roster: glob `${CLAUDE_PLUGIN_ROOT}/agents/*.md` for agent names (filename minus `.md`) and `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` for skill names (parent directory name). If `${CLAUDE_PLUGIN_ROOT}` doesn't resolve, locate the plugin's own `agents/` and `skills/` directories with Glob instead (same fallback `/studious-init` uses for templates) — don't guess a path.
2. Compare that shipped roster against what this session actually has registered: the agent names available to the Agent tool and the skill names available to the Skill tool, both already present in your own system context for this conversation (the "Available agent types" and available-skills listings injected at session start). Do not re-derive this list by reading files a second time — the whole point is to check what got registered, not what's on disk. If that system-context listing itself isn't present or isn't clearly readable this session (its format is a Claude Code internal, not a stable contract this command controls), do not guess — report plugin health as **Inconclusive**: "could not read this session's registered agent/skill listing — re-run in a session where it's present" rather than emitting a false Critical.
3. Any shipped agent or skill absent from the session's registered list is **Critical** — name it and state the consequence: "`<name>` shipped but not registered this session — `/gate-audit` (or the matching gate) silently runs without this lane."
4. Report the roster size as counts derived from step 1 (e.g. "15 agents, 4 skills shipped") — never hardcode a count.

If everything shipped is registered, report **OK** with the counts.

## 3. Context docs

For each of PRODUCT.md, DESIGN.md, CLAUDE.md in the consuming project's root:

- **Missing** — the file doesn't exist. **Important** — "gates and reviews that read this file have no project context."
- **Stub** — the file exists, but for PRODUCT.md/DESIGN.md, compare its section content against the placeholder comments shipped at `${CLAUDE_PLUGIN_ROOT}/templates/PRODUCT.md` / `${CLAUDE_PLUGIN_ROOT}/templates/DESIGN.md` (same plugin-root resolution and Glob fallback as section 2). Two classes of template heading are exempt from this check, since the template itself marks them optional: any heading whose text contains `(if applicable)` (e.g. PRODUCT.md's "Secondary persona (if applicable)"), and DESIGN.md's `## Per-surface conventions` subsections except whichever match a surface actually listed in the doc's own `## Surfaces` table — the template's own instructions say to delete the rest, so their absence or placeholder state isn't a stub signal. The `## Surfaces` table records fixed machine tokens, not headings, so translate with this exact mapping: `web` → `### Web`, `cli` → `### CLI`, `plugin` → `### Plugin / prompt tooling`, `tui` → `### TUI`, `api` → `### API`, `report` → `### Report / export`; `library` has no matching subsection at all (a pure library keeps this doc minimal per the template's own instruction). If **any** other required section (each remaining `##`/`###` heading in the template) still contains only its template's placeholder comment rather than replaced prose, classify the whole doc as stub — a partially-filled doc is exactly the half-false-confidence state this check exists to catch. Report as **Important** — "`<doc>` is still the shipped template (`<section>` unedited) — gates read it but get no real project context." A doc that also carries its own `<!-- FILL IN: ... -->` author TODOs on top of real prose is **not** a stub on that basis alone — that's a populated doc with open follow-ups, not the original scaffold.
- **Populated** — anything else. Report **OK**.

CLAUDE.md has no shipped template (`templates/CLAUDE.md` does not exist), so it only ever reports **missing** or **populated** — never stub.

## 4. Flow-state hygiene

`.studious/` accumulates one work file per feature and one state file per epic, and nothing collects them automatically. When they pile up, `/work-on` with no argument stops being able to answer "what's next" — it has to ask you to pick from a list instead (#237).

Count them with `gate-ledger work-list` (one line per work file) and by globbing `.studious/epics/*.json`. Classify:

- **More than 10 work files** — **Important** — "`/work-on` will ask you to choose from N features instead of resuming one. Run `gate-ledger gc`." That verb collects work files whose flow ended (phase `done`/`stopped`) or whose branch is gone, and epic state for epics that shipped, though it keeps a work file with unread scope-delta data (#244) for 14 days, or until you read it and `gate-ledger gc --force` past it sooner.
- **1–10** — **OK**, with the count.
- **A work file whose branch no longer exists** — name it: `gc` will collect it, and until then it is noise in every `work-list` read.

Report the counts, never the full list — this is a health check, not an inventory. And recommend `gc`; never run it. Same recommend-only posture as everything else here.

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

**Flow state**
- [OK|Important] <n work files, m epics> — <"clean" | "`/work-on` will ask you to choose from n features; run `gate-ledger gc`">

### Summary
<N> critical, <N> important, <N> ok. This is a health check, not a gate — no verdict token, nothing recorded to the ledger.
```

Findings use the same severity vocabulary as every other Studious command (`Critical` · `Important` · `Track` — see `reference/severity-rubric.md`); nothing in this command reaches `Track`, since every check here is binary (a tool either silently breaks something or it doesn't).
