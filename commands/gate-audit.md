---
description: Run the audit suite — security, code quality, docs, architecture, UX, and frontend in parallel, plus an optional accessibility pass
allowed-tools: Read, Glob, Grep, Bash, Task, Write
---

# Audit gate — all auditors

Run every auditor in parallel against the current branch. This combines the backend audit suite, frontend audit suite, and accessibility checks into a single pass.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

Establish the changeset under review before spawning anyone: compute the merge-base with the default branch (`git merge-base HEAD origin/main`, falling back to `origin/master` or the repo's default branch) and treat the diff from that base to `HEAD` as the changeset. Pass this explicit scope to every auditor so "this branch" / "this changeset" means the same diff for all of them.

## Launch all auditors in parallel

Spawn auditors 1–6 — plus auditor 8 when a pre-mortem register exists — as subagents simultaneously; do not run them sequentially. Auditor 7 is an inline external check, described below.

Auditors 5–7 (ux, frontend, accessibility) are web-specific. Skip them when either condition holds:
- **Project-level:** DESIGN.md has a `## Surfaces` table that lists no web surface, **and the repo confirms it** — no `web`-surface signal as defined in `/extract-design-system` Step 1 (that list is canonical; don't restate it here, to avoid drift). Both must hold. Note "No web surface (DESIGN.md + repo agree) — frontend audits skipped." Their cross-surface and per-surface consistency is covered by `/deep-review interface`, not by this gate. Require the repo check because the `## Surfaces` table can be stale: if it claims no web surface but the repo shows web-framework signal, the doc is wrong — do NOT skip; run the auditors and flag the doc for re-extraction. If DESIGN.md has no `## Surfaces` table at all (a doc predating this format), assume a web surface may exist and fall through to the per-changeset check. Default to running, not skipping.
- **Per-changeset:** the changeset has no frontend changes (no modified template, component, CSS, or JS files). Note "No frontend changes detected — frontend audits skipped."

### Backend auditors

1. **@agent-security-auditor** — Review all changes on this branch for OWASP top 10 vulnerabilities, authentication bypasses, injection risks, and exposed secrets.

2. **@agent-code-auditor** — Review the full changeset for code duplication, complexity, naming consistency, and error handling patterns.

3. **@agent-doc-auditor** — Analyze documentation gaps. Are new APIs documented? Are inline comments adequate? Do this branch's new, changed, or removed commands, install steps, flags, or file paths contradict what the README claims? Flag README drift introduced by the changeset, not just missing sections.

4. **@agent-architecture-auditor** — Review architectural decisions in this changeset. Does it fit existing patterns? Any coupling concerns? Scalability issues?

### Frontend auditors (run these for any branch with UI changes)

5. **@agent-ux-reviewer** — Review all UI changes against DESIGN.md. Check layout, information hierarchy, spacing consistency, interaction clarity, component consistency, and responsive behavior.

6. **@agent-frontend-reviewer** — Review frontend code changes for component architecture, state management patterns, data fetching, render performance, and bundle impact.

7. **Web Interface Guidelines (external, optional, with vendored fallback)** — This check depends on the `web-design-guidelines` skill, which ships separately, not with Studious. If it's installed, invoke the `web-design-guidelines` skill against all modified frontend files (components, pages, layouts) to check accessibility, keyboard support, form behavior, focus management, semantic HTML, and animation. Unlike auditors 1–6, this runs inline rather than as a parallel subagent. If the skill isn't installed, fall back to `reference/accessibility-checklist.md` and review the same modified frontend files against its keyboard access, contrast, focus management, and semantic HTML sections directly — don't skip the pass. Note which path ran ("via web-design-guidelines skill" or "via vendored accessibility-checklist.md fallback") in the summary.

### Pre-mortem verification (runs only when a register exists)

Locate the register before spawning: look for `docs/studious/premortems/*.md` in the changeset diff; if none, take the most recently modified file under `docs/studious/premortems/`; if there are several candidates, ask the user which one rather than guessing. If no register exists at all, note "No pre-mortem register on this branch — pre-mortem verification skipped." and move on.

8. **@agent-premortem-auditor** — Verify the pre-mortem register at the resolved path against this changeset. Lane: `technical`. Report a per-item verdict (NOT REALIZED / REALIZED / CAN'T VERIFY) with evidence; the `product`-lane items belong to `/gate-acceptance`, not this gate.

## After all auditors return

The auditors don't share a severity vocabulary — map each one's labels into the report's three tiers before compiling, per the canonical ladder and per-auditor mapping in `reference/severity-rubric.md`; consult it, don't restate it.

Then compile a unified audit report:

### Summary
One line per auditor: agent name, number of findings by severity, pass/fail.

### Critical findings (blocks merge)
All findings classified as critical/blocking across all auditors, grouped by file. If multiple auditors flag the same file, consolidate their findings together.

### Important findings (should fix)
All non-critical but important findings, grouped by category (security, code quality, documentation, architecture, UX, frontend, accessibility).

### Track findings (revisit later)
Everything else. Don't expand on these — just list them.

### Verdict
Based on the findings, recommend one of:
- **PASS** — No critical findings. Safe to proceed to product acceptance gate.
- **FIX AND RE-AUDIT** — Critical findings listed. Fix these, then re-run `/gate-audit`.
- **NEEDS DISCUSSION** — Architectural or product-level concerns that aren't simple fixes.

## Record the verdict

After stating the verdict, record it to the local gate ledger so the PR-time reminder
can be specific. Run (substituting the verdict token you just assigned — `PASS`,
`FIX AND RE-AUDIT`, or `NEEDS DISCUSSION`):

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger" record --gate audit --verdict "PASS"
```

The ledger is local and gitignored — it never enters the repo. If `${CLAUDE_PLUGIN_ROOT}`
did not resolve or the script is not found, tell the user the verdict could not be
recorded to the gate ledger — do not skip silently.
