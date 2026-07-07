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

If all three succeed, report each as **OK**.

## 2. Plugin health

Every agent and skill Studious ships must actually be registered this session — a file present on disk with malformed frontmatter fails to register but leaves no error, silently dropping a `/gate-audit` lane or a natural-language trigger.

1. Locate the plugin's own shipped roster: glob `${CLAUDE_PLUGIN_ROOT}/agents/*.md` for agent names (filename minus `.md`) and `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` for skill names (parent directory name). If `${CLAUDE_PLUGIN_ROOT}` doesn't resolve, locate the plugin's own `agents/` and `skills/` directories with Glob instead (same fallback `/studious-init` uses for templates) — don't guess a path.
2. Compare that shipped roster against what this session actually has registered: the agent names available to the Agent tool and the skill names available to the Skill tool, both already present in your own system context for this conversation (the "Available agent types" and available-skills listings injected at session start). Do not re-derive this list by reading files a second time — the whole point is to check what got registered, not what's on disk.
3. Any shipped agent or skill absent from the session's registered list is **Critical** — name it and state the consequence: "`<name>` shipped but not registered this session — `/gate-audit` (or the matching gate) silently runs without this lane."
4. Report the roster size as counts derived from step 1 (e.g. "15 agents, 4 skills shipped") — never hardcode a count.

If everything shipped is registered, report **OK** with the counts.

## 3. Context docs

For each of PRODUCT.md, DESIGN.md, CLAUDE.md in the consuming project's root:

- **Missing** — the file doesn't exist. **Important** — "gates and reviews that read this file have no project context."
- **Stub** — the file exists, but for PRODUCT.md/DESIGN.md, compare its section content against the placeholder comments shipped at `${CLAUDE_PLUGIN_ROOT}/templates/PRODUCT.md` / `${CLAUDE_PLUGIN_ROOT}/templates/DESIGN.md` (same plugin-root resolution and Glob fallback as section 2). Two classes of template heading are exempt from this check, since the template itself marks them optional: any heading whose text contains `(if applicable)` (e.g. PRODUCT.md's "Secondary persona (if applicable)"), and DESIGN.md's `## Per-surface conventions` subsections (`### Web`, `### CLI`, `### Plugin / prompt tooling`, `### TUI`, `### API`, `### Report / export`) except whichever match a surface actually listed in the doc's own `## Surfaces` table — the template's own instructions say to delete the rest, so their absence or placeholder state isn't a stub signal. If **any** other required section (each remaining `##`/`###` heading in the template) still contains only its template's placeholder comment rather than replaced prose, classify the whole doc as stub — a partially-filled doc is exactly the half-false-confidence state this check exists to catch. Report as **Important** — "`<doc>` is still the shipped template (`<section>` unedited) — gates read it but get no real project context." A doc that also carries its own `<!-- FILL IN: ... -->` author TODOs on top of real prose is **not** a stub on that basis alone — that's a populated doc with open follow-ups, not the original scaffold.
- **Populated** — anything else. Report **OK**.

CLAUDE.md has no shipped template (`templates/CLAUDE.md` does not exist), so it only ever reports **missing** or **populated** — never stub.

## Output

```
## Studious doctor

**Tooling**
- [OK|Important|Critical] <check>: <status, and consequence if not OK>

**Plugin health**
- [OK|Critical] <n agents, m skills shipped and registered | list of unregistered names with consequence>

**Context docs**
- [OK|Important] PRODUCT.md: <populated | stub (<section>) | missing> — <consequence if not OK>
- [OK|Important] DESIGN.md: <same>
- [OK|Important] CLAUDE.md: <populated | missing> — <consequence if not OK>

### Summary
<N> critical, <N> important, <N> ok. This is a health check, not a gate — no verdict token, nothing recorded to the ledger.
```

Findings use the same severity vocabulary as every other Studious command (`Critical` · `Important` · `Track` — see `reference/severity-rubric.md`); nothing in this command reaches `Track`, since every check here is binary (a tool either silently breaks something or it doesn't).
