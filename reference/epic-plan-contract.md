# Epic-plan contract — lookup data

`/work-through`'s plan piece proposes a decomposition; the user approves it. This file
names what an approvable plan must contain — the analogue of
`reference/design-doc-contract.md` one level up. A plan missing a required element isn't
a style nit: the driver schedules from this data, so a gap here becomes an unscheduled
or unjudgeable story later.

## Required elements

| Element | Why the driver needs it |
|---------|-------------------------|
| Epic goal statement | One sentence. The epic-finale `/gate-acceptance` judges the integrated result against it, not against any single story. |
| Stories | Each: a short slug, a title, and its source issue(s). Splitting or merging GitHub issues is proposed here, never applied to GitHub. |
| Acceptance criteria per story | What the story's `/gate-acceptance` run must be able to verify — concrete and observable. "Works" is not a criterion. |
| Dependency edges | The DAG the scheduler runs. Only real sequencing dependencies: an edge claims the downstream story cannot be designed or built until the upstream one lands. |
| Gate profile per story | Which of design → design-review → build → audit → acceptance run for this story. Default is all five. Audit is never trimmed. Trimming is proposed by the planner, decided by the user at approval. |
| Epic pre-mortem | Cross-story failure modes — integration seams, shared-schema drift, sequencing risk — written to `docs/studious/premortems/<epic-slug>-epic.md` and verified at the epic finale by `agents/premortem-auditor.md`. |
| Concurrency cap | How many stories may run at once. Default 3. |

## Approval

Approval is explicit — the user says so after seeing the full plan. Silence, a partial
comment, or "looks interesting" is not approval. What the user approves is what gets
recorded: if they trim, reorder, or drop stories, record the edited version. Approving
the plan is the batched should-we-build for every story in it — no per-story decide
gate runs later. A story added mid-flight gets its own scoped decide pass and explicit
approval of its DAG placement before it joins the schedule.
