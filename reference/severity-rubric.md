# Severity rubric — canonical tiers, the one row `/review` still maps, and the epic driver's local roster

Canonical three-tier severity ladder for `/review`. Its judge lanes are gauntlet's and emit
these tiers directly (its findings contract, `docs/findings-contract.md` §5), so `/review`
maps one vocabulary only: the `web-design-guidelines` skill's, on its inline lane-8 path,
which returns no findings document. The per-auditor tables survive in one place — the
"Local roster" section at the end — for `workflows/epic-driver.js`, which still dispatches
the local `agents/` until #334 S2. The periodic review family (`agents/review-*.md`) already
emits directly in this vocabulary.

## The three tiers

- **Critical** — blocks merge. Fix now.
- **Important** — should fix. Fix this cycle.
- **Track** — not urgent; log it and revisit later.

Never introduce a fourth tier.

## The one label → tier row

| Lane | → Critical (blocks merge) | → Important (should fix) | → Track |
|------|---------------------------|--------------------------|-----------------|
| web-design-guidelines (a11y) | blocking a11y failures (no keyboard access, contrast failures on core flows) | other a11y gaps | polish |

## Objective anchors — what a Critical must cite

A tier is not a self-assessment: a Critical must cite the objective anchor its lane owns — a fact
a reader can check without re-running the reviewer's judgment. For every gauntlet judge the
anchor is named in gauntlet's charter (`charter.md` under its `reference/` directory, "Anchors —
what a critical must cite"), and gauntlet's `scripts/report.py` records an anchorless critical
as `important` at ingest and names the demotion in the compiled report. **A finding labelled
Critical that cites no anchor is recorded Important instead** — the gate door applies this before
the ledger write, and the compiled report names the anchor that was missing. The one anchor
studious states for `/review` itself is the inline lane's (the local roster's are in the
section at the end, which is what the epic driver's compile reads):

| Lane | A Critical must cite |
|------|----------------------|
| web-design-guidelines (a11y) | the named guideline that fails (keyboard access, contrast ratio) and the core flow it fails on |

Disposition history is the second filter: a finding already recorded `rejected-as-noise` on this
episode (`bin/gate-ledger episode-finding`) is settled, and re-raising it at a higher tier does not
make it a Critical. Re-opening a settled finding needs a new anchor, not a new adjective.

## Local roster — read by `workflows/epic-driver.js` until #334 S2

The epic driver still dispatches the local `agents/` — its `AUDITORS` constant, plus
`product-reviewer` and `premortem-auditor` on the acceptance path — and those agents emit
their own labels. Its `epicLedgerInstruction` maps them through the first table and holds
every Critical to the second before the ledger write, where an unanchored Critical would park
a story's whole dependent subtree. `/review` never reads these tables; both die with that
dispatch (S2) and the agents (S4). A new local auditor registers a row in both here.

### Label → tier

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
| premortem-auditor | BLOCKER (REALIZED) | SHOULD FIX (REALIZED, register-integrity) | OBSERVATION (CAN'T VERIFY / staleness) |
| product-reviewer (criteria conformance) | BLOCKER | SHOULD FIX | MINOR, OBSERVATION |

### Anchors — what a Critical must cite

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
| ux-reviewer | a reproducible broken flow: the steps, the expected result, the observed one |
| frontend-reviewer | a reproducible broken flow: the steps, the expected result, the observed one |
| premortem-auditor | the register item, by id, marked REALIZED, plus the evidence that realized it |
| product-reviewer (criteria conformance) | the stated acceptance criterion, quoted, that the changeset does not deliver |
