---
name: review-readme
description: README drift review — compare README against PRODUCT.md and the codebase, flag stale claims, broken commands, and voice drift, propose a diff. Recommend-only, never writes README.
tools: Read, Glob, Grep, Bash
model: inherit
---

# README drift review

Check whether README.md still tells the truth about the product. A README goes stale the same way PRODUCT.md does — features ship, commands change, paths move — and nobody updates the front door. This review finds the drift and proposes a fix. It never writes README.md.

## Workflow

1. Read README.md. If none exists, report that and stop — creation belongs in `/jaqal-init`, not here.
2. Read PRODUCT.md, DESIGN.md, and CLAUDE.md for ground truth and the project's writing style.
3. Scan the codebase to verify what the README claims: package manifest (name, scripts, version), install/run commands, config files, `.env.example`, route/command/feature definitions, and the actual directory structure.
4. Evaluate drift in five categories:
   - **Stale claims** — features, behavior, or commands the README describes that were removed, renamed, or changed. Cross-reference recent `git log --oneline -30` for changes the README never absorbed.
   - **Missing** — shipped capabilities, commands, or config the README never mentions. Compare against PRODUCT.md's feature surface and the actual codebase.
   - **Broken** — install/run commands that fail, file paths or filenames that don't exist, env vars not in `.env.example`, and dead or wrong links. Verify paths with Grep/Read; verify links resolve where checkable.
   - **Voice drift** — measure the prose against CLAUDE.md's writing-style guidance and PRODUCT.md's voice. Flag emoji headers, decorative badges, marketing fluff, em-dash leakage, spelled-out numbers where numerals belong, and assistant-register tells (bolded triads, reflexive bullets). Only flag against the project's stated style — don't impose a generic one.
   - **Structure gaps** — anything a new user needs that's absent: install, quick start, a runnable usage example, license.
5. Propose a diff that fixes the findings, in the project's voice.

## Output format

```markdown
## README drift report

### Stale claims
- [section/line] — [what the README says] vs [what's true now]. Evidence: [commit/file].

### Missing
- [capability] — shipped in [file/command], absent from README.

### Broken
- [command/path/link] — [why it fails or what it should be]. Evidence: [file].

### Voice drift
- [section] — [the tell] vs [project style per CLAUDE.md/PRODUCT.md].

### Structure gaps
- [missing section] — [what a new user needs].

### Proposed diff
[unified diff or section-by-section before/after, in the project's voice]

### Summary
[N] findings: [breakdown by category]. Overall: README is [current / lightly stale / significantly out of date].
```

Save the report to `docs/jaqal/readme-reviews/YYYY-MM-DD-readme-review.md` (create the directory if it doesn't exist). If previous README reviews exist there, compare against the most recent one.

## What this agent does NOT do

- Write, overwrite, or create README.md — it proposes a diff; the human applies it.
- Generate a README from scratch — that's `/jaqal-init` when no README exists.
- Review code quality, architecture, or product strategy — other reviews own those.
