---
description: Identify open GitHub issues that should be closed — resolved, obsolete, or duplicated. Recommend-only, never modifies issues.
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Backlog hygiene

Identify open GitHub issues that should be closed because they've been resolved, made obsolete, or duplicated by other issues. Run weekly or before milestones.

> Requires GitHub Issues via the `gh` CLI. PRODUCT.md may link a different tracker (Linear, Jira) — this command only reads GitHub Issues. If the project tracks work elsewhere, it doesn't apply.

Read PRODUCT.md and CLAUDE.md first for product context.

## Run the analysis

Spawn @agent-backlog-hygiene to fetch the open issues, cross-reference each against git history, PRODUCT.md, and the most recent review reports, and compile the report.

Output format and evidence rules are the agent's — see `agents/backlog-hygiene.md`'s `## Output` section, including its `## Close (resolved)`, `## Close (obsolete)`, `## Merge duplicates`, `## Summary`, and `## Could not verify` sections.

This command is recommend-only. It never closes, comments on, or modifies any issues.
