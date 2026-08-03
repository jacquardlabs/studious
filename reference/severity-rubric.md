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
| operability-auditor | Critical, High | Medium | Low |
| dependency-auditor | Critical, High | Medium | Low |
| code-auditor | Critical | High, Medium | Low |
| test-auditor | Critical | High, Medium | Low |
| architecture-auditor | Critical | High, Medium | Low |
| prompt-auditor | Critical | High, Medium | Low |
| doc-auditor | — (docs rarely block; escalate only if a wrong command/path ships) | High | Medium, Low |
| ux-reviewer | VISUAL BUG | INCONSISTENCY | IMPROVEMENT, SUGGESTION |
| frontend-reviewer | BUG | PERFORMANCE, ARCHITECTURE | CLEANUP |
| web-design-guidelines (a11y) | blocking a11y failures (no keyboard access, contrast failures on core flows) | other a11y gaps | polish |
| premortem-auditor | BLOCKER (REALIZED) | SHOULD FIX (REALIZED, register-integrity) | OBSERVATION (CAN'T VERIFY / staleness) |
| product-reviewer (criteria conformance) | BLOCKER | SHOULD FIX | MINOR, OBSERVATION |

A new auditor registers its own row in both tables here rather than requiring a hand-edit anywhere else.

## Objective anchors — what a Critical must cite

A tier is not a self-assessment. Critical blocks merge, so a Critical is only a Critical when it
cites the objective anchor its lane owns: a fact a reader can check without re-running the
reviewer's judgment. **A finding labelled Critical that cites no anchor is recorded Important
instead** — the gate door that records findings applies this before the ledger write, and the
compiled report names the anchor that was missing. This is not a challenge to the reviewer's
skill; it is what keeps "Critical" a claim about the changeset rather than a claim about how the
reviewer feels about the changeset.

| Auditor | A Critical must cite |
|---------|----------------------|
| security-auditor | a named signature from `reference/security-checklist.md` (SSRF, Command, XSS, Path traversal, …) plus the traced path from untrusted input to that sink, at `file:line` |
| infra-auditor | the resource or config property in the diff, at `file:line`, and the failure it produces — data loss, public exposure, or outage |
| operability-auditor | the failure this changeset makes undetectable or unrecoverable, and the missing alarm, log, or rollback path by name |
| dependency-auditor | a named advisory (CVE/GHSA) reachable from the code, or the exact version delta the changeset introduces |
| code-auditor | a behavior delta: the input, the code path at `file:line`, and the wrong output or crash it produces |
| test-auditor | a named test or command whose result the changeset changes, or a load-bearing behavior with no test at all, named |
| architecture-auditor | the contract that broke and the downstream consumer that relies on it, named by path |
| prompt-auditor | the instruction or invariant the prompt surface contradicts, quoted, with the file it comes from |
| doc-auditor | a command or path the docs state that does not exist or does not work as written (docs rarely reach Critical at all) |
| ux-reviewer / frontend-reviewer | a reproducible broken flow: the steps, the expected result, the observed one |
| web-design-guidelines (a11y) | the named guideline that fails (keyboard access, contrast ratio) and the core flow it fails on |
| premortem-auditor | the register item, by id, marked REALIZED, plus the evidence that realized it |
| product-reviewer (criteria conformance) | the stated acceptance criterion, quoted, that the changeset does not deliver |

Disposition history is the second filter: a finding already recorded `rejected-as-noise` on this
episode (`bin/gate-ledger episode-finding`) is settled, and re-raising it at a higher tier does not
make it a Critical. Re-opening a settled finding needs a new anchor, not a new adjective.
