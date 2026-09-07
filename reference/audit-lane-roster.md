# Audit lane roster — the one table pinning `/review` and `epic-driver.js` together

Canonical source for which audit lanes exist, one per row. Two independently
hand-maintained surfaces enumerate lanes without deriving from a shared source —
`commands/review.md`'s work-episode numbered list (14 entries) and
`workflows/epic-driver.js`'s `const AUDITORS` array (11 entries, dispatched generically
by `auditRound`/`finaleAuditRound`) — and nothing stopped them drifting apart silently
(#274). This file is the guard: `tests/python/test_audit_lane_roster.py` parses both
surfaces and asserts every lane either surface names is a row here, and that the `In
AUDITORS?` column matches what the array actually contains. It is a pinning test on one
source, not maintenance on three — change a lane here first, then in whichever surface
actually dispatches it.

This file does not restate the routing rule itself; the **Routing** column cites
`reference/audit-routing-signals.md` (file-pattern lists) or `commands/review.md` (the
content-judged and conditional lanes, which have no file-pattern proxy).

## The roster

| # | Lane | Gauntlet judge | Routing | In `AUDITORS`? |
|---|------|-----------------|---------|-----------------|
| 1 | security | `security-auditor` | unconditional | yes |
| 2 | code | `code-auditor` | unconditional | yes |
| 3 | doc | `doc-auditor` | unconditional | yes |
| 4 | architecture | `architecture-auditor` | unconditional | yes |
| 5 | test | `test-auditor` | unconditional | yes |
| 6 | ux | `ux-reviewer` | changeset-routed — Frontend signal | yes |
| 7 | frontend | `frontend-reviewer` | changeset-routed — Frontend signal | yes |
| 8 | accessibility | `accessibility-auditor` | changeset-routed — Frontend signal (or the inline `web-design-guidelines` skill when installed) | no |
| 9 | infra | `infra-auditor` | changeset-routed — Infrastructure signal | yes |
| 10 | operability | `operability-auditor` | changeset-routed — content-judged, no file-pattern signal (`reference/audit-routing-signals.md`'s own "Auditor 10" section) | yes |
| 11 | dependency | `dependency-auditor` | changeset-routed — Dependency signal | yes |
| 12 | prompt | `prompt-auditor` | changeset-routed — Prompt signal | yes |
| 13 | pre-mortem verification | `premortem-auditor` | conditional — only when a pre-mortem register exists on the branch (`commands/review.md`, "Pre-mortem verification (only when a register exists)") | no |
| 14 | criteria conformance | `product-reviewer` | unconditional — always runs (`commands/review.md`, "Criteria conformance (always runs)") | no |

**Gauntlet judge** names the `gauntlet:<judge>` dispatch every lane resolves to. All 14
reach one — including 13 and 14, which is why `inline` is not used here: that word is
already pinned in this repo (`commands/review.md`'s lane 8, `reference/severity-rubric.md`'s
"inline lane-8 path") to mean a check the door runs itself, in its own turn, with no
subagent Task at all. Lanes 13 and 14 are ordinary `gauntlet:<judge>` Task dispatches —
`gauntlet:premortem-auditor` and `gauntlet:product-reviewer` — just not ones
`epic-driver.js` reaches by iterating the generic `AUDITORS` array the way lanes 1–12 are:
each has its own dedicated call site (`acceptancePremortemDispatchPrompt`,
`acceptanceProductReviewPrompt`), and criteria conformance has a second, non-gauntlet path
too — under the `delivery-boundary` acceptance altitude, `criteriaConformanceRound` runs a
plain mechanical evidence check with no gauntlet dispatch at all (see the "Every `no` here"
section below). What the `In AUDITORS?` column answers is membership in that one array,
never whether a gauntlet judge is involved.

## Every `no` here is a deliberate split, not a bug

Three lanes are absent from `AUDITORS` on purpose, each already load-bearing elsewhere in
this repo — a pinning test exists precisely so a *future* gap reads as a real drift
signal against this table, not so today's three get "fixed" into the array:

- **accessibility (8)** — `workflows/epic-driver.js`'s comment directly above `AUDITORS`
  (jacquardlabs/studious#271, tracked further by #274 itself) explains why: a Workflow
  script cannot detect whether the consuming session has the optional
  `web-design-guidelines` skill installed, so shipping the Task fallback
  (`gauntlet:accessibility-auditor`) unconditionally would diverge silently from the
  interactive gate on any project where the skill *is* installed. The gap is rendered
  visibly on every compiled report where the frontend signal matches
  (`joinReports`'s "not covered on the epic path" block) rather than papered over.
- **pre-mortem verification (13)** — `tests/python/test_audit_premortem_scope.py` pins
  this: pre-mortem verification is a dedicated acceptance/finale step
  (`acceptancePremortemDispatchPrompt`, the finale's `premortemDispatchPrompt`), never a
  fixed `AUDITORS` dispatch lane, because the register rides into every story worktree
  via the ordinary `git worktree add` from the epic branch — adding it to `AUDITORS`
  would make the generic audit-gate fan-out fire it on every story regardless of whether
  a register exists, which is exactly the phantom-missing-lane bug that test file
  documents fixing.
- **criteria conformance (14)** — likewise a dedicated acceptance-gate step
  (`acceptanceProductReviewPrompt` dispatching `gauntlet:product-reviewer`, or, under the
  `delivery-boundary` acceptance altitude, `criteriaConformanceRound`'s plain mechanical
  check with no gauntlet dispatch at all) — never a member of the audit gate's generic
  fan-out. `commands/review.md`'s interactive door bundles it into the same work
  episode/`audit` ledger gate as lanes 1–13; `epic-driver.js` splits it into a separate
  `acceptance` gate instead. Both reach the same lane; neither is wrong.

If a future row's `In AUDITORS?` disagrees with what `const AUDITORS` actually contains
and it is *not* one of the three splits above with a comment explaining it at the
`AUDITORS` definition, treat it as the real drift #274 was filed to catch, not as a
fourth deliberate split to document away.

## Consumers that must stay in sync

Update this table first when a lane is added, retired, or its `AUDITORS` membership
changes, then:

- `tests/python/test_audit_lane_roster.py` — parses this table against
  `commands/review.md`'s work-episode lane list and `workflows/epic-driver.js`'s
  `AUDITORS` array; a lane named in either surface but missing here, or an `AUDITORS`
  membership mismatch, fails the test.
- `commands/review.md`'s work-episode numbered list — the lane's own dispatch prose and
  skip rule live there; this table names it, never restates its rubric.
- `workflows/epic-driver.js`'s `AUDITORS` array and its preceding comment — the actual
  dispatch membership and, for any lane deliberately excluded, the reasoning this table
  summarizes.
