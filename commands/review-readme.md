---
description: README drift review — flag stale claims, broken commands, and voice drift against the codebase, then propose a diff. Recommend-only, never writes README.
allowed-tools: Read, Glob, Grep, Bash, Task
---

# README drift review

Check whether README.md still tells the truth about the product. Run it after a release, after a batch of features, or whenever the README feels behind. It proposes a diff; you apply it.

Read PRODUCT.md, DESIGN.md, and CLAUDE.md first for product context and the project's writing style.

## Run the analysis

Spawn @agent-review-readme to:

1. Read README.md. If none exists, report that and stop — creation belongs in `/jaqal-init`.
2. Scan the codebase to verify what the README claims: manifest, install/run commands, config, `.env.example`, feature definitions, directory structure.
3. Flag drift in five categories:
   - **Stale claims** — described features or commands that were removed, renamed, or changed
   - **Missing** — shipped capabilities the README never mentions
   - **Broken** — commands, paths, env vars, or links that don't match the codebase
   - **Voice drift** — prose that breaks CLAUDE.md's writing style or PRODUCT.md's voice (emoji, badges, marketing fluff, em-dash leakage)
   - **Structure gaps** — install, usage, or license a new user needs
4. Propose a diff that fixes the findings, in the project's voice.

## Output

A drift report grouped by the five categories, a proposed diff, and a summary verdict (current / lightly stale / significantly out of date). Saved to `docs/jaqal/readme-reviews/YYYY-MM-DD-readme-review.md`.

This command is recommend-only. It never writes, overwrites, or creates README.md — it proposes the diff for you to apply.
