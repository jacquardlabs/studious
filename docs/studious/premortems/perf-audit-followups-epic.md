# Epic pre-mortem — perf-audit-followups

Recorded at plan approval (2026-07-21). Cross-story failure modes only — each story's
own pre-mortem (if any) covers its local risks. Verified per item at the epic finale
by `@agent-premortem-auditor`: REALIZED / NOT REALIZED / CAN'T VERIFY.

## 1. `commands/gate-audit.md` is a three-way overlap, not a pair

`audit-a11y-parallel-dispatch` (#158, auditor-8 dispatch block, ~line 84),
`audit-doc-split` (#159, the "After all auditors return" compile section, ~lines
112-160), and `evidence-list-dedupe` (#162, the "Resolve the branch's evidence log"
block, ~lines 28-34) all edit this one file, in three non-adjacent sections. Merges
likely apply clean given the non-overlapping ranges, but the driver's merge-fix-then-
park mechanism (one mechanical attempt, abort → park) has three chances to collide
here instead of two.

**Signal it's realized:** any of the three stories parks specifically on a merge
conflict in `commands/gate-audit.md`.

## 2. `bin/gate-ledger` is a second overlap

`epic-reconcile-verb` (#160) and `evidence-list-dedupe` (#162) both add new verb/flag
surface to the same file, including its dispatch `case` table at the bottom.

**Signal it's realized:** a merge conflict in `bin/gate-ledger`'s dispatch block.

## 3. `workflows/epic-driver.js` is a third overlap

`audit-doc-split` (#159) edits `auditFanIn()`'s literal compile-prompt string;
`acceptance-retry-visibility` (#142), if it ships a retry-visibility mechanism, likely
touches the gate-dispatch/retry loop elsewhere in the same file.

**Signal it's realized:** a merge conflict in `workflows/epic-driver.js`.

## 4. `acceptance-retry-visibility` (#142) may not be fixable at this layer at all

The silent retry the issue describes happened at the Workflow-tool substrate
(dedup/memoization keys, dispatch retry), which a workflow script has no documented
API to introspect. This story's design phase may conclude there's no signal to hook a
`work-log RETRY` entry off of, and ship a heuristic/staleness mitigation or a
documented limitation instead of the originally-imagined direct fix. Approved at plan
time as an accepted possible outcome (full 5-gate profile, with the understanding this
may park at acceptance as NEEDS DISCUSSION rather than SHIP).

**Signal it's realized:** the design doc proposes a mitigation or documents a
limitation rather than a direct work-log RETRY mechanism — this is not evidence the
story failed its brief, only that the investigation resolved to a real constraint.

## 5. Doc-pointer drift

Once `audit-doc-split` lands, any future edit to the compilation rules must go into
`reference/audit-compilation.md`, never back into `gate-audit.md` directly, or the
split silently re-forks into two diverging copies.

**Signal it's realized:** a later PR touches compilation-rule prose in
`commands/gate-audit.md` itself instead of `reference/audit-compilation.md`.

## 6. Ledger backward-compatibility

`epic-reconcile-verb` and `evidence-list-dedupe` both read pre-existing `.studious/`
JSON/JSONL files written before either change exists — every gate/work/epic file and
every evidence log captured before this epic merges.

**Signal it's realized:** either verb throws, or silently misreports, when handed a
real pre-existing file from before this epic that predates whatever new derived
fields or flags it introduces.

## 7. Installed-vs-edited-copy gap

This `/work-through` session runs the *installed* plugin copy of `epic-driver.js` and
`gate-ledger` (the marketplace cache path, v2.24.0), not this worktree's edited
copies. No story's fix is live for this epic's own run — only for epics driven after
this one merges, releases, and the installed plugin version bumps. Every story here is
verified by the gates reading the edited files as data (diffs, structure, tests), not
by this epic's own runtime behavior exercising them.

**Signal it's realized:** a parked-story reason or the finale attributes an
observation from this epic's own execution (reconcile round-trip count, evidence log
size, audit-doc read cost) to a story's fix working or not working, rather than to
this installed-vs-edited gap.
