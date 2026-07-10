# Epic pre-mortem — gate-ledger-robustness

**Epic goal:** Retire the debt the M1 finale audit and the 2026-07-07 cross-project
prompt audit surfaced: unify and harden the contract-injection guarantee across all
three dispatch mechanisms, fix real scheduler and ledger defects, add missing workflow
tooling, and remove prompt and doc duplication and gate-audit calibration gaps, so the
automated work-through path carries the same rigor as the supervised one and the
gate-ledger tooling itself stays maintainable as it grows.

**Source:** milestone M2 · **Stories:** contract-injection-unify (#110, #111),
scheduler-fixes (#104), workflows-js-lint (#103), gate-ledger-json-writer (#102),
premortem-hook-awareness (#100), gate-doc-commit-ordering (#99), prompt-contract-dedup
(#92), gate-audit-verdict-robustness (#91).

These are the cross-story failure modes recorded at plan time. The epic finale's
`premortem-auditor` checks each against the integrated diff and reports
REALIZED / NOT REALIZED / CAN'T VERIFY.

## Failure modes

1. **`workflows/epic-driver.js` three-way merge seam.** contract-injection-unify,
   scheduler-fixes, and gate-doc-commit-ordering each rewrite this file — the CONTRACT
   const/dispatch functions, the cycleMembers/indegree scheduling code, and the finale
   prompt strings, respectively. The regions are logically independent, but whichever
   of the three lands last is likely to hit a textual merge conflict against the other
   two.
   *Mitigation:* no DAG edge — the conflict is textual, not logical. A merge-conflict
   park on the third story to land is a merge-order artifact, not a design failure;
   resolve mechanically and re-run `/work-through` rather than treating it as blocked.

2. **`agents/ux-reviewer.md` and `agents/code-auditor.md` shared-file seam.**
   prompt-contract-dedup (citation de-duplication) and gate-audit-verdict-robustness
   (severity-mapping and threshold fixes) both edit these two files for unrelated
   reasons.
   *Mitigation:* same as above — expect a merge conflict on whichever lands second;
   resolve mechanically, do not park as a genuine block.

3. **`bin/gate-ledger` sequencing risk (the one real dependency).** scheduler-fixes and
   gate-ledger-json-writer both rewrite `cmd_epic_story_set` (and possibly
   `cmd_work_set`) in `bin/gate-ledger` — scheduler-fixes to namespace work-file slugs,
   gate-ledger-json-writer to consolidate the mutating-verb boilerplate. If the writer
   refactor is built against the pre-namespacing code, it will silently omit the
   namespacing-era duplication and need a second pass.
   *Mitigation:* DAG edge recorded at plan time — gate-ledger-json-writer depends on
   scheduler-fixes; the scheduler must land first.

4. **Trimmed gate profiles assume the design phase is never skipped.** Five of the
   eight stories trim design-review but none trim design itself, because
   `epic-driver.js`'s build-dispatch prompt (`workerPrompt`, ~line 133) unconditionally
   tells the worker to implement "the story's recorded design doc" via
   `gate-ledger work-get` → `.designDoc` — there is no branch for a story with no
   design doc. If a future amendment to this epic trims a story's `design` phase, the
   build dispatch will point the worker at a design doc that was never recorded.
   *Mitigation:* do not amend any story's gate profile to drop `design` mid-flight
   without first confirming `epic-driver.js` has been changed to support it — treat
   this as a standing constraint on amendments, not just a plan-time note.
