# Severity rubric — canonical tiers and per-auditor mapping

Canonical source for the three-tier severity ladder used by `/gate-audit` and the label→tier
mapping that glues the auditors' five different severity vocabularies to it. `commands/gate-audit.md`
cites this file instead of embedding the mapping table. The periodic review family
(`commands/deep-review.md`, `agents/review-*.md`) already emits directly in this vocabulary
and needs no mapping.

## The three tiers

- **Critical** — blocks merge. Fix now.
- **Important** — should fix. Fix this cycle.
- **Track** — not urgent; log it and revisit later.

Never introduce a fourth tier; map every auditor's labels into these three.

## Per-auditor label → tier mapping

| Auditor | → Critical (blocks merge) | → Important (should fix) | → Track |
|---------|---------------------------|--------------------------|-----------------|
| security-auditor | Critical, High | Medium | Low |
| infra-auditor | Critical, High | Medium | Low |
| code-auditor | Critical | High, Medium | Low |
| architecture-auditor | Critical | High, Medium | Low |
| doc-auditor | — (docs rarely block; escalate only if a wrong command/path ships) | High | Medium, Low |
| ux-reviewer | VISUAL BUG | INCONSISTENCY, IMPROVEMENT | SUGGESTION |
| frontend-reviewer | BUG | PERFORMANCE, ARCHITECTURE | CLEANUP |
| web-design-guidelines (a11y) | blocking a11y failures (no keyboard access, contrast failures on core flows) | other a11y gaps | polish |
| premortem-auditor | BLOCKER (REALIZED) | SHOULD FIX (REALIZED, register-integrity) | OBSERVATION (CAN'T VERIFY / staleness) |

A new auditor registers its own row here rather than requiring a hand-edit anywhere else.
