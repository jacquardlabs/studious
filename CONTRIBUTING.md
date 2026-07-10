# Contributing to Studious

Thanks for your interest in improving Studious. Here's how to contribute.

## Reporting issues

Open an issue for bugs, unclear documentation, or suggestions. Include:

- What you expected to happen
- What actually happened
- Which command or agent was involved
- Your Claude Code version (`claude --version`)

## Proposing changes

1. **Open an issue first** for anything beyond a typo fix. Describe what you want to change and why. This saves everyone time if the change doesn't fit the project's direction.
2. **Fork and branch** from `main`.
3. **Make your changes.** Follow the patterns in existing files — agent frontmatter, command frontmatter, and directory structure are intentional.
4. **Open a PR** against `main` with a clear description of what changed and why.

## What makes a good contribution

- **Agent or command improvements** — better prompts, clearer instructions, more useful output formats
- **New agents or commands** that fit the existing workflow (gates, reviews, audits, backlog management)
- **Bug fixes** — commands that don't work as documented
- **Documentation** — README improvements, better examples

## Structure conventions

```
agents/       — Agent definitions (name, description, tools, model in frontmatter)
bin/          — Executables used by commands (e.g. gate-ledger for gate verdicts, /work-on's per-feature state, and /work-through's per-epic state)
commands/     — Slash commands (description, allowed-tools in frontmatter)
scripts/      — CI helper scripts (link checking, manifest validation)
skills/       — Natural-language trigger shims (skills/<name>/SKILL.md)
hooks/        — Shipped hook scripts + hooks.json (e.g. the PR-time gate reminder)
reference/    — Curated rubrics agents read at audit time (e.g. reference/idioms/<lang>.md)
templates/    — Scaffold files created by /studious-init
tests/        — Python and shell tests for commands and CI scripts
```

- Agents do the work. Commands orchestrate agents or provide standalone workflows.
- Skills are trigger shims: a tightly-scoped `description` lets a gate fire from natural language, and the body delegates to the matching command instead of duplicating it.
- Every agent and command reads PRODUCT.md, DESIGN.md, or CLAUDE.md for project context.
- Review reports save to `docs/studious/` subdirectories in the user's project, not to the plugin itself.
- Commands that produce output are recommend-only — they report, never modify external state (issues, PRs, files outside `docs/studious/`). **Exception:** the gate commands record their verdicts, and `/work-on` records per-feature flow position, to local, gitignored `.studious/` state in the consuming project; the ledger auto-appends `.studious/` to `.gitignore` on first write.
- **Workers never gate; gates never build.** `/work-through` dispatches worker agents (design docs, implementation, fixes) and gate agents (the existing gate commands) as separate agents with no shared context. A worker must never record a verdict; a gate agent must never write code. The `.studious/` exception above extends to `/work-through`: it records epic and story flow state to the same local, gitignored stores.

## Naming conventions

Names encode two things — whether something is an action or a role, and what scope it works at. Follow the existing shape; the prefix/suffix split is deliberate, not drift.

- **Commands are actions** — an action prefix plus its target: `gate-` (per-change checkpoints), `review-`/`deep-review` (periodic health), `extract-` (one-time scaffolding), `backlog-` (issue triage), `work-` (flow navigation: `work-on` one piece at a time, `work-through` a whole epic). The verb goes in front.
- **Agents are either a 1:1 reviewer or a role.** Periodic, project-scoped reviewers share their command's `review-*` name (currently spawned by `/deep-review`). Changeset specialists spawned by a fan-out command (`/gate-audit`, the gates) are named by role: `<domain>-auditor` for technical/rule checks (security, code, doc, architecture), `<domain>-reviewer` for human-judgment checks (product, ux, frontend).
- **One fan-out command, many subagents.** Parallel checks belong to subagents under a single entry point (`/gate-audit`, `/deep-review`), not to their own top-level commands. Don't add a command per check.
- **Skills are named for the intent they detect** — `evaluate-feature-idea`, `review-design-before-build`, `acceptance-check-before-merge` — not for the command they call. The `description` carries the trigger; keep it conservative (fire on explicit intent, list what it should NOT match) so a gate never interrupts when it isn't wanted.

## Model assignments

Pin by stakes, not by habit. An agent's `model` is `opus` when its core job is high-stakes reasoning or human judgment — where a weaker model ships worse decisions — and `inherit` (the session model) for mechanical, rule-based, or inventory work.

- **`opus`** — security, architecture, and product/UX judgment: `security-auditor`, `infra-auditor`, `architecture-auditor`, `product-reviewer`, `ux-reviewer`, `review-architecture`, `review-product-health`, `review-security-health`.
- **`inherit`** — code hygiene, docs, tests, frontend code, inventory sweeps, and triage: `code-auditor`, `doc-auditor`, `test-auditor`, `frontend-reviewer`, `review-codebase-health`, `review-interface-health`, `review-readme`, `backlog-priorities`, `backlog-hygiene`.

Don't pin to a bare tier like `sonnet` — use `inherit` so the agent tracks the user's session model.

## What we won't merge

- Changes that make agents modify issues, PRs, or external state without explicit user action
- Features that duplicate what [Superpowers](https://github.com/obra/superpowers) already handles (brainstorming, planning, TDD, execution)
- Agents that bundle multiple concerns (security + code quality in one agent) — each agent stays in its lane

## Code of conduct

Be respectful and constructive. We're all here to make better tools.
