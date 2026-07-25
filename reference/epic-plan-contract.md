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
| Settled forks per story | The product/scope questions answered at the plan piece's one interview, recorded per story as `decisions`. Every phase is dispatched to a subagent with no human in its loop, so an unanswered fork can only be guessed or parked — this is where the human answers instead. Distinct from acceptance criteria: criteria say what "done" means, decisions say which of two defensible designs was chosen. Absent for a story whose forks were all obvious. |
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

The fork interview runs before approval, not after: the user is approving a plan whose
open product questions are already answered, not one that will discover them mid-run.
Cap the interview at 10–12 questions for the whole epic, admitting only forks that are
both product/scope level and answerable before any story is built. Implementation forks
surface mid-build and depend on earlier stories' output — those park, and the story
appears in "Needs you". Approval is the interview's deadline, so a fork raised after it
follows the mid-flight-story rule above.

## Consumers that must stay in sync

- `commands/work-through.md` — the only writer. Its plan piece runs the interview and
  records each element through `gate-ledger epic-set` / `epic-story-set`; the field
  names in its `--criteria` / `--decisions` / `--deps` / `--gates` flags are this
  table's elements.
- `bin/gate-ledger` — `epic-story-set` stores them; a new required element here needs a
  flag there, or the plan piece has nowhere to put it.
- `workflows/epic-driver.js` — reads them back. `ctx()` threads `criteria` and
  `decisions` into every dispatch prompt; `deps` and `gates` drive the scheduler. An
  element the driver never reads is a documentation-only element, and should say so.
