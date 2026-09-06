## README drift report

### Summary
README is significantly out of date. 4 findings: 1 stale claim about epic PR handling; 3 missing capabilities shipped in M0 (#314–#317). M0 introduced a fully unattended entry path (ready-labeled issue → intake filter → viva stamp → auto-fire) and browser-resolvable parks, neither mentioned. Biggest concern: epic finale now opens the PR itself, but README says PR is the user's responsibility.

### Stale claims
- [Important · Confirmed] Line 157 `/ship` flow — says "then the PR is yours" as if the user always opens it. At epic scale (M0, #320–#326), the epic finale dispatch auto-opens the PR after design, audit, and acceptance gates pass. Story scale remains true (user opens it). Evidence: `reference/epic-orchestration.md` "Epic finale" section (line 675: "pushes the epic branch and opens its PR"), commit `3c83794` feat: epic exit, merge authority, and async approval (#253, #312, #311) (#320).

### Missing
- [Important · Confirmed] Fully unattended entry path — shipped in M0 (#314–#316): ready-labeled issue → `scripts/intake` (deterministic eligibility filter) → viva stamp on brief → `scripts/stamp-bridge` (fires `/next` locally) → `scripts/epic-supervisor` (re-fire loop for unattended cycles). README mentions viva for `/shape` and `/build` human sign-off but not async-approval flow (brief written by agent, stamped before human sees it). Evidence: commits `8b3dbc2` (scripts/intake), `5539beb` (scripts/stamp-bridge), `b104d42` (scripts/epic-supervisor).
- [Important · Confirmed] Browser-resolvable parks — shipped in M0 (#317): `scripts/park-packet` (writes QA round for each parked story) and `scripts/park-resolve` (applies browser-submitted decision). README mentions parks as a concept but not that they can be resolved in the browser under supervision. Evidence: commit `5fe0349` (scripts/park-packet, scripts/park-resolve).
- [Track · Confirmed] Epic finale auto-merge behavior — README doesn't state whether `auto-merge` tier (defined in PRODUCT.md #312) ever gets exercised or if it's advisory only. Not a breakage, but a gap in explaining the merge authority matrix the README references indirectly. Evidence: PRODUCT.md "Merge authority" section describes three tiers; README makes no mention of which stories exercise which tier or when.

### Broken
- None found. All referenced commands, paths, and files resolve. Links to `reference/`, `.github/workflows/`, PRODUCT.md, and DESIGN.md all correct.

### Voice drift
- [Track · Confirmed] Line 157 ambiguity — "then the PR is yours" reads as if true for all scales, but the statement is only fully accurate at story scale. At epic scale, it's no longer the user's responsibility post-finale. Not misleading per se (the user still reviews the PR), but needs scope qualification.

### Structure gaps
- [Important · Confirmed] Entry paths section missing — README briefly mentions `/next` as "the only door you have to remember" but doesn't explain that epic entry has two modes: (1) interactive approval at the terminal (existing), (2) async-approval (agent-authored brief, viva stamp, auto-fire). Under M0, supervisors and unattended systems follow path 2; a new user needs to know both exist.
- [Track · Confirmed] Epic PR and merge-class routing — README doesn't mention that some stories route to `auto-merge` (CI green + 0 critical findings), others need human approval, others never run unattended. The merge-authority tier should appear in the epic flow description alongside appetite and acceptance-altitude.

### Proposed diff

```markdown
## The flow

/bet     →  scores the idea, ranks it against the backlog, sets the appetite
   ↓
/shape   →  interview, drafted design doc, viva sign-off per section
   ↓
/review  →  design episode; writes the pre-mortem register on a pass
   ↓
/build   →  plans, then builds — fresh executor per task, script-verified, evidence captured
   ↓
/review  →  work episode; up to 13 specialist lanes, plus criteria conformance
   ↓
/review --delivery  →  delivery episode; does this deliver what the bet promised?
   ↓
/ship    →  evidence table, follow-ups, build report, then for stories the PR is yours; for epics the finale opens it
```

**At milestone scale,** the same `/next` proposes a story plan (dependency order, acceptance criteria, per-story gate profile and merge class, an epic-level pre-mortem), interviews you once for the whole epic, shows you what it will cost, and stops for approval. Nothing runs before you approve. Then dispatched agents drive the unattended stories in parallel worktrees, and hand back the ones a judge can't verify mechanically.

**Entry modes:** An epic may enter interactively — you approve the plan at a terminal — or asynchronously. In async mode, an agent authors the brief, records it `proposed`, and waits for a viva stamp. Once stamped (`scripts/stamp-bridge`), `/next` fires automatically. For unattended epics that park at human-judgment gates, `scripts/park-packet` writes a browser QA round and `scripts/park-resolve` applies the human's decision without a terminal. Full contract: [`reference/epic-orchestration.md`](reference/epic-orchestration.md).

**Merge authority:** Every story in the plan is classed as `auto-merge` (CI green + 0 critical findings), `human-approve` (a code owner merges), or `never-unattended` (always supervised). The class is recorded at approval and routes the story to its outcome path. See PRODUCT.md's "Merge authority" for the full matrix.

---

Replace the existing "At milestone scale" paragraph and "Full contract" line (lines 164–169) with the three paragraphs above.

For `/ship` line 157, change:

```markdown
/ship    →  evidence table, follow-ups, build report, then the PR is yours
```

to:

```markdown
/ship    →  evidence table, follow-ups, build report, then for stories the PR is yours; for epics the finale opens it
```

## Residual

Verified all referenced files and commands exist and resolve correctly. No external links tested (offline environment). No prior readme reviews found to compare against (first review). Compared against baseline: PRODUCT.md (current known problems, merge authority, epic-specific sections), DESIGN.md (vocabulary and gate verdicts), git log (M0 commits #320–#326 dated 2026-09-06 and earlier dated commits back through #314–#317), and `reference/epic-orchestration.md` (Epic finale section, async-approval, park handling). 

The README's claim-set is otherwise current with code; no other gates or commands have been removed or renamed since v3.2.0 (2026-08-04). The new scripts are implementation details that don't change the user-facing door surface, but they enable a flow the README should surface so a user adopting supervision or unattended-epic patterns knows it exists.

