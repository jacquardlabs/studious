---
description: Product acceptance review after implementation, before merge
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Does the result deliver?

Code is built, tests pass, audits are clean. This gate checks whether the implementation actually delivers the intended experience. Clean code that ships a bad feature is still a bad feature.

Read PRODUCT.md first.

## Part 1 — Product review

Invoke @agent-product-reviewer to review the implementation on the current branch against the original design doc and PRODUCT.md. This is a post-implementation product acceptance review.

## Part 2 — Implementation walkthrough

Walk through every user-facing change on this branch yourself, using @agent-product-reviewer's "When reviewing an IMPLEMENTATION" checklist (`agents/product-reviewer.md`) as the lens — Part 1 already ran that checklist as a subagent; don't re-derive the questions here, just apply them directly as you walk the branch.

Close with one gate-specific question the checklist doesn't ask: **One complaint** — what's the single thing a real user would complain about if we shipped this as-is? Be specific. There's always something.

## Part 3 — Verdict

Map the product-reviewer's severities to this gate's verdict:

- **SHIP** — implementation delivers the intended experience; only MINOR/OBSERVATION findings.
- **FIX AND RE-CHECK** — one or more SHOULD FIX findings, or a BLOCKER fixable with targeted work. List them with severity, then re-run this gate.
- **HOLD** — a BLOCKER that's a fundamental gap between design intent and implementation, needing rework beyond quick fixes.

For FIX AND RE-CHECK items, be specific enough that they can go directly into the engineering chain as fix tasks.

## Record the verdict

After stating the verdict, record it to the local gate ledger so the PR-time reminder
can be specific. Run (substituting the verdict token you just assigned — `SHIP`,
`FIX AND RE-CHECK`, or `HOLD`):

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger" record --gate acceptance --verdict "SHIP"
```

The ledger is local and gitignored — it never enters the repo. If `${CLAUDE_PLUGIN_ROOT}`
did not resolve or the script is not found, tell the user the verdict could not be
recorded to the gate ledger — do not skip silently.
