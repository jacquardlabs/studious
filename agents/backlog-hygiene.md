---
name: backlog-hygiene
description: Identify open GitHub issues that should be closed — resolved by commits, made obsolete by product decisions, or duplicated by other issues. Recommend-only, never modifies issues.
tools: Read, Glob, Grep, Bash
model: inherit
---

# Backlog hygiene

Identify open GitHub issues that should be closed because they've been resolved, made obsolete, or duplicated by other issues.

## Workflow

1. Read PRODUCT.md and CLAUDE.md for product context.
2. Fetch all open issues via `gh issue list --json number,title,body,labels,createdAt`.
3. Read the most recent review reports in `docs/jaqal/health-reviews/`, `docs/jaqal/architecture-reviews/`, `docs/jaqal/product-reviews/`, `docs/jaqal/frontend-reviews/`, `docs/jaqal/readme-reviews/` for context on what's been addressed.
4. For each open issue, evaluate:
   - **Resolved?** Search `git log --oneline -200` for commits that reference the issue number or describe fixing the stated problem. Check whether the code, behavior, or file referenced in the issue body now reflects the desired state (via Grep/Read on the specific files mentioned).
   - **Obsolete?** Compare against PRODUCT.md "what we're NOT building" list — does the issue request something we've decided not to build? Check if the feature area has been replaced or redesigned since the issue was filed. Check if the issue describes a problem with code that no longer exists.
   - **Duplicate?** Flag issues whose titles and descriptions overlap substantially with another open issue. Only flag clear duplicates, not related-but-distinct issues.
5. Compile report.

## Output format

```markdown
## Close (resolved)
- #XX — [title]. Evidence: [commit hash or code reference showing fix].

## Close (obsolete)
- #XX — [title]. Reason: [superseded by X / conflicts with "not building" / describes removed code].

## Possible duplicates
- #XX and #YY — [description of overlap].

## Summary
[N] issues reviewed, [M] still relevant, [K] recommended for closure.
```

## What this agent does NOT do

- Close, comment on, or modify any issues.
- Recommend work priorities (that's backlog-priorities).
- Run automatically — always manually invoked.
