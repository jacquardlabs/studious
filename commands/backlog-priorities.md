---
description: Curate a ranked shortlist from open GitHub issues based on your current intent — tech debt, maintenance, polish, or new initiative
argument-hint: "[tech-debt | maintenance | polish | new-initiative] (omit for overview)"
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Backlog priorities

Help decide what to work on next by curating a ranked shortlist from open issues.

> Requires GitHub Issues via the `gh` CLI. PRODUCT.md may link a different tracker (Linear, Jira) — this command only reads GitHub Issues. If the project tracks work elsewhere, it doesn't apply.

Read PRODUCT.md and CLAUDE.md first for product context.

## Run the analysis

Pass `$ARGUMENTS` to @agent-backlog-priorities as the work-mode intent. If it's empty, the agent runs overview mode (top-1 per area); if it names an intent, the agent runs deep-dive mode for that intent. Spawn @agent-backlog-priorities to fetch the open issues, cross-reference them against review findings and PRODUCT.md, and rank them.

Output format and evidence rules are the agent's — see `agents/backlog-priorities.md`'s `## Output` section, including its per-mode format (deep-dive vs overview) and its closing "What I couldn't assess" line.

This command is recommend-only. It never starts work, creates branches, or modifies issues.
