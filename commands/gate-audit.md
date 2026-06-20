---
description: Run the audit suite — security, code quality, docs, architecture, UX, and frontend in parallel, plus an optional accessibility pass
allowed-tools: Read, Glob, Grep, Bash, Task, Write
---

# Audit gate — all auditors

Run every auditor in parallel against the current branch. This combines the backend audit suite, frontend audit suite, and accessibility checks into a single pass.

Read CLAUDE.md, PRODUCT.md, and DESIGN.md first.

## Launch all auditors in parallel

Spawn auditors 1–6 as subagents simultaneously — do not run them sequentially. Auditor 7 is an inline external check, described below.

### Backend auditors

1. **@agent-security-auditor** — Review all changes on this branch for OWASP top 10 vulnerabilities, authentication bypasses, injection risks, and exposed secrets.

2. **@agent-code-auditor** — Review the full changeset for code duplication, complexity, naming consistency, and error handling patterns.

3. **@agent-doc-auditor** — Analyze documentation gaps. Are new APIs documented? Are inline comments adequate? Do this branch's new, changed, or removed commands, install steps, flags, or file paths contradict what the README claims? Flag README drift introduced by the changeset, not just missing sections.

4. **@agent-architecture-auditor** — Review architectural decisions in this changeset. Does it fit existing patterns? Any coupling concerns? Scalability issues?

### Frontend auditors (run these for any branch with UI changes)

5. **@agent-ux-reviewer** — Review all UI changes against DESIGN.md. Check layout, information hierarchy, spacing consistency, interaction clarity, component consistency, and responsive behavior.

6. **@agent-frontend-reviewer** — Review frontend code changes for component architecture, state management patterns, data fetching, render performance, and bundle impact.

7. **Web Interface Guidelines (external, optional)** — This check depends on the `web-design-guidelines` skill, which ships separately, not with Jaqal. If it's installed, run `/web-interface-guidelines` against all modified frontend files (components, pages, layouts) to check accessibility, keyboard support, form behavior, focus management, semantic HTML, and animation. Unlike auditors 1–6, this runs inline rather than as a parallel subagent. If the skill isn't available, note "accessibility check skipped — web-design-guidelines not installed" and move on.

## After all auditors return

Compile a unified audit report:

### Summary
One line per auditor: agent name, number of findings by severity, pass/fail.

### Critical findings (blocks merge)
All findings classified as critical/blocking across all auditors, grouped by file. If multiple auditors flag the same file, consolidate their findings together.

### Important findings (should fix)
All non-critical but important findings, grouped by category (security, code quality, UX, accessibility, architecture).

### Minor findings (track for later)
Everything else. Don't expand on these — just list them.

### Verdict
Based on the findings, recommend one of:
- **PASS** — No critical findings. Safe to proceed to product acceptance gate.
- **FIX AND RE-AUDIT** — Critical findings listed. Fix these, then re-run `/gate-audit`.
- **NEEDS DISCUSSION** — Architectural or product-level concerns that aren't simple fixes.

If the branch has no frontend changes (no modified template, component, CSS, or JS files), skip auditors 5-7 and note "No frontend changes detected — frontend audits skipped."
