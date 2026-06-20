---
description: Identify open GitHub issues that should be closed — resolved, obsolete, or duplicated. Recommend-only, never modifies issues.
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Backlog hygiene

Identify open GitHub issues that should be closed because they've been resolved, made obsolete, or duplicated by other issues. Run weekly or before milestones.

> Requires GitHub Issues via the `gh` CLI. PRODUCT.md may link a different tracker (Linear, Jira) — this command only reads GitHub Issues. If the project tracks work elsewhere, it doesn't apply.

Read PRODUCT.md and CLAUDE.md first for product context.

## Run the analysis

Spawn @agent-backlog-hygiene to:

1. Fetch all open issues via `gh issue list`.
2. Read the most recent review reports in `docs/jaqal/health-reviews/`, `docs/jaqal/architecture-reviews/`, `docs/jaqal/product-reviews/`, `docs/jaqal/frontend-reviews/`, `docs/jaqal/readme-reviews/` for context on what's been addressed.
3. For each open issue, check:
   - **Resolved?** — Search git log for commits that reference the issue or fix the stated problem. Check if the code now reflects the desired state.
   - **Obsolete?** — Compare against PRODUCT.md "what we're NOT building." Check if the feature area has been replaced or redesigned.
   - **Duplicate?** — Flag issues with substantial overlap. Only flag clear duplicates, not related-but-distinct issues.
4. Compile the report with evidence for each recommendation.

## Output

The report groups issues into:
- **Close (resolved)** — with commit hash or code reference as evidence
- **Close (obsolete)** — with reason (superseded, conflicts with "not building", describes removed code)
- **Possible duplicates** — pairs of issues with description of overlap
- **Summary** — counts of reviewed, still-relevant, and recommended-for-closure

This command is recommend-only. It never closes, comments on, or modifies any issues.
