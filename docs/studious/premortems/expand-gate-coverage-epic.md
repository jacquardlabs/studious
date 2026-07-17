# Epic pre-mortem — expand-gate-coverage

Recorded at plan approval (2026-07-17). Cross-story failure modes only — each story's
own pre-mortem (if any) covers its local risks. Verified per item at the epic finale
by `@agent-premortem-auditor`: REALIZED / NOT REALIZED / CAN'T VERIFY. Note for the
finale reader: this epic's own gates run the *installed plugin* fan-out, so the two
lanes this epic adds are not live for its own audits — their absence from this epic's
own runs is expected, not evidence of a wiring failure.

## 1. Fan-out merge collision

`dep-auditor` and `prompt-auditor` both insert a lane into the same fan-out list in
`commands/gate-audit.md` and the same routing table in
`reference/audit-routing-signals.md`. The DAG sequences them (`prompt-auditor` depends
on `dep-auditor`) specifically to avoid a concurrent edit to those regions — but a bad
conflict resolution, or a `prompt-auditor` design phase that reads the pre-epic
snapshot instead of the landed `dep-auditor` shape, can silently drop one lane from
the fan-out.

**Signal it's realized:** the epic-tip `commands/gate-audit.md` or
`reference/audit-routing-signals.md` lists only one of the two new lanes, or
`prompt-auditor`'s design doc doesn't reference the landed `dep-auditor` diff.

## 2. Roster-count drift

README, CONTRIBUTING.md, and CLAUDE.md carry agent-roster counts (the shared prompt
contract's carrier count among them). Two new agents make every stale count wrong —
exactly the drift #116 (M9) exists to guard. Each story owns its own doc updates, but
counts are cross-cutting: story A can correct a count story B then invalidates.

**Signal it's realized:** any agent-count claim at the epic tip disagrees with
`ls agents/ | wc -l` or with the prompt-contract carrier list.

## 3. Contract divergence in a new lane

A new auditor ships without the shared prompt-contract posture — injection-defense
preamble, read-only/diff-scope convention, output-row schema, calibrate-don't-suppress
closer — or pins a model against the stakes convention. The fleet standard fragments
exactly where it's supposed to be load-bearing.

**Signal it's realized:** `agents/dependency-auditor.md` or `agents/prompt-auditor.md`
lacks any of the four contract blocks or breaks the naming/model conventions in
CONTRIBUTING.md.

## 4. Always-on lane cost

In an LLM-native repo every diff touches prompt files, so the prompt-auditor lane
fires on every `/gate-audit` run there — including every future run in this repo. A
weak auto-skip or a bloated rubric regresses gate latency and cost, worsening the M6
problem this plugin is separately trying to fix.

**Signal it's realized:** the lane's skip condition can't describe a realistic diff
that skips it in an LLM-native repo, or its rubric dispatches sub-checks the diff
doesn't warrant.

## 5. Journal scope creep

`decision-journal`'s value is memory that *informs* — "you evaluated this on <date>:
DEFER because X — has X changed?" If the implementation drifts into auto-verdicting
(pre-filling or short-circuiting the gate from a prior entry), the gate stops being
judgment and becomes cache replay, violating the judgment-is-the-spine principle.

**Signal it's realized:** `/gate-should-we-build` emits a verdict sourced from the
journal without running its own evaluation, or `/backlog-priorities` demotes an issue
solely because a prior DEFER exists.

## 6. Cross-story contract skew

`success-metrics` (#120) changes the design-doc contract mid-epic while `dep-auditor`,
`prompt-auditor`, and `decision-journal` write design docs under it. A story's design
doc satisfies whichever contract is current at its design time; the finale must not
retro-fail an earlier story's doc against a row that landed after its design review
passed.

**Signal it's realized:** a finale or acceptance finding cites a missing
success-metrics section in a design doc whose design-review predates the
`success-metrics` story's landing.
