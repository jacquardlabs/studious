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

Pass `$ARGUMENTS` to @agent-backlog-priorities as the work-mode intent. If it's empty, the agent runs overview mode (top-1 per area); if it names an intent, the agent runs deep-dive mode for that intent. Spawn @agent-backlog-priorities to:

1. Fetch all open issues via `gh issue list`.
2. Read the most recent deep review summary and individual review reports.
3. Resolve the work mode:
   - **Intent supplied** (`$ARGUMENTS` names one of tech-debt / maintenance / polish / new-initiative) — **deep-dive mode**: filter, score, and present the full ranked list (3-5 items) for that intent.
   - **No argument** — **overview mode**: pick the top priority from each of the 4 intent areas and present them together in a compact format.
4. Filter and rank issues by:
   - Severity from review reports (Critical/Important findings rank higher)
   - Product alignment (addresses PRODUCT.md known problems or principles)
   - Unblocking potential (enables other issues or features)
   - Context freshness (code areas with recent commits are cheaper to tackle)
5. Present results in the format for the active mode (see Output).

## Output

**Deep-dive mode** — full ranked list with:
- **Recommended (top pick)** — with 2-3 sentence rationale referencing PRODUCT.md or review findings
- **Also strong candidates** — 2-3 alternatives with one-line rationale each
- **Honorable mentions** — additional options worth considering

**Overview mode** — top-1 pick per intent area in compact format, closing with a hint to run `/backlog-priorities [area]` for the full list.

This command is recommend-only. It never starts work, creates branches, or modifies issues.
