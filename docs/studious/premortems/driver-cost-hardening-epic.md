# Epic pre-mortem — driver-cost-hardening

Recorded at plan approval (2026-07-12). Cross-story failure modes only — each story's
own pre-mortem (if any) covers its local risks. Verified per item at the epic finale
by `@agent-premortem-auditor`: REALIZED / NOT REALIZED / CAN'T VERIFY.

## 1. Shared-function rewrite collision

`crash-hardening` wraps the worker/gate/merge `agent()` call sites and the finale
report assembly; `delta-scoped-reaudit` rewrites the re-audit dispatch scoping inside
the exact same functions (`runGate`, `auditRound`, `finaleGate`) in
`workflows/epic-driver.js`. The DAG sequences them (`delta-scoped-reaudit` depends on
`crash-hardening`) specifically to avoid two stories independently reshaping that
region — but sequencing in time doesn't guarantee `delta-scoped-reaudit`'s design
phase actually reads and designs against the landed shape rather than the
pre-approval snapshot.

**Signal it's realized:** `delta-scoped-reaudit`'s design doc doesn't reference the
landed `crash-hardening` diff, or the two stories' changes to the same functions
conflict in a way the merge agent's one mechanical attempt can't resolve.

## 2. Delta-scoping fails open instead of closed

The entire premise of #130 is a cost/rigor tradeoff — narrowing what gets re-audited
necessarily narrows what gets re-verified. A bug in lane-attribution or fix-delta
computation that silently omits a lane which should have re-run doesn't fail loud; it
just produces an unearned PASS, which is worse than the O(auditors) cost problem this
epic exists to fix. Acceptance criterion 4 on that story (fail closed to a full
re-audit when attribution is ambiguous) is the mitigation; whether it's actually
implemented that way, versus merely asserted, is the open question.

**Signal it's realized:** the story ships without a test exercising the
ambiguous/missing-attribution path specifically, or that path is observed to narrow
scope rather than widen it back to full.

## 3. Standalone/epic-driven drift

`workflows/epic-driver.js`'s own comments note it already bypasses
`commands/gate-audit.md` and duplicates the auditor fan-out itself. Implementing the
delta-scoping rule in only one of the two surfaces (the code path or the prompt path)
leaves the other running the old, unscoped, full-cost re-audit — silently
reintroducing exactly the cost problem #130 was filed against, on whichever path
didn't get the fix.

**Signal it's realized:** a `/gate-audit` re-run on a standalone (non-epic) branch and
an epic-driven re-audit produce different dispatch scopes for the same class of
fix-and-retry verdict.

## 4. This epic's own execution doesn't dogfood its own fix

This `/work-through` session runs the *installed plugin* copy of `epic-driver.js`
(the marketplace cache path), not this worktree's edited copy. Neither story's fix is
live for this epic's own run — only for epics driven after this one merges, releases,
and the installed plugin version bumps. Not a build risk, but worth naming so a
mid-run crash or an unscoped re-audit observed *during this epic's own execution* is
not mistaken for evidence the fix didn't work.

**Signal it's realized:** the finale or a parked-story reason misattributes a crash or
a full-width re-audit observed during this epic's own run to either story's fix
failing, rather than to the installed-vs-edited-copy gap.

## 5. Ledger schema backward-compatibility

If `delta-scoped-reaudit`'s design resolves the "where is prior-round lane attribution
stored" question by extending `bin/gate-ledger record`'s stored schema (needed for the
standalone path, where re-invocations are separate command runs with no shared
in-memory state), every existing `.studious/gates/*.json` file written before this
change lacks the new field. The PR-time hook and `/work-on`'s evidence check both read
that file directly and must not choke or misread on its absence.

**Signal it's realized:** a gate-ledger read path throws, or silently misreports a
verdict, when handed a pre-existing gate JSON file that predates the schema addition.
