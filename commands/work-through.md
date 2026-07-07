---
description: Drive a whole milestone or epic through the gate flow with dispatched agents — plan once for approval, then run everything runnable, stopping only for judgment calls
argument-hint: "[milestone, epic issue, or label] (omit to keep driving the epic in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write
---

# Work through an epic

Drive a whole milestone through the same gate flow `/work-on` walks one piece at a
time. This command owns scheduling — which stories run, in what order, and when a
verdict escalates to the user — never the gates' judgments and never the how of
building. Two modes, resolved by state rather than flags: no epic in flight → the plan
piece; an approved epic → the driver.

**The posture — non-negotiable:**

- **Gates are unbypassable.** Run the gate commands' workflows verbatim; never soften,
  reinterpret, or skip a verdict. Tokens are canonical in `reference/gate-vocabulary.md`.
- **Lanes stay separate.** Gate agents never build; worker agents never gate; the two
  never share context. A gate judges the diff and the doc, never a worker's transcript.
- **GitHub is read-only.** Never create or edit issues; never open PRs — after the
  finale the branch is the user's (`gh pr create`).
- **Judgment verdicts always stop the story** and wait for the user. Autonomy never
  absorbs a RETHINK, NEEDS DISCUSSION, or HOLD.
- **Nothing runs before the user approves the plan.**

Read PRODUCT.md at the project root first. If `gate-ledger` is not on `PATH`, stop —
this flow cannot run without recorded state. Say so and point at `/work-on` for the
supervised, evidence-first flow instead.

## Resolve the epic

`gate-ledger epic-list` shows epics in flight (slug, status, landed/total, branch, title).

- **`$ARGUMENTS` is empty** — if exactly one epic has status `approved`, `running`, or
  `ready`, drive it. If several, list them and ask which — don't guess. If none, invite
  `/work-through [milestone, epic issue, or label]`.
- **`$ARGUMENTS` matches an epic in flight** (slug or title) — drive that one.
- **Anything else starts a new epic.** Resolve it read-only with `gh`:
  - a milestone name or number → `gh issue list --milestone "<M>" --state open --json number,title,body,labels`
  - an issue reference → `gh issue view <N> --json number,title,body` (for an epic
    issue, follow its checklist and linked issues too)
  - a label → `gh issue list --label "<L>" --state open --json number,title,body,labels`

  Then run the plan piece.

## Plan piece — runs once, ends at approval

1. Read PRODUCT.md, DESIGN.md, and CLAUDE.md.
2. Propose a decomposition satisfying `reference/epic-plan-contract.md`: stories with
   slugs, source issues, acceptance criteria, dependency edges, a gate profile each, an
   epic goal statement, a concurrency cap, and an epic pre-mortem. Present the whole
   plan — the user can only approve what they can see.
3. Stop and iterate. The user trims, reorders, re-scopes, drops. Nothing is recorded
   and nothing runs until they explicitly approve.
4. On approval, record exactly what was approved. Derive `<slug>` from the epic title:

   ```bash
   gate-ledger epic-set --slug "<slug>" --title "<title>" --source "<milestone M | issue #N | label L>" \
     --goal "<goal statement>" --branch "epic/<slug>" --concurrency <cap> --status approved
   gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --title "<story title>" \
     --source "issue #N" --criteria "<criteria>" --deps "<dep-a,dep-b>" --gates "<profile>"
   ```

   (one `epic-story-set` per story), then:

   - Write the epic pre-mortem register to `docs/studious/premortems/<slug>-epic.md`
     and record it: `gate-ledger epic-set --slug "<slug>" --premortem "<path>"`.
   - Create the integration branch and its dedicated worktree — never touch the user's
     checkout:

     ```bash
     git branch "epic/<slug>"
     git worktree add ".studious/worktrees/<slug>/__epic" "epic/<slug>"
     ```

5. Close with the report block below. Driving starts on the next invocation — approval
   and execution never share one.

## Driver — every later invocation

If the epic's status is still `approved`, mark the run started:
`gate-ledger epic-set --slug "<slug>" --status running`. Then loop steps 1–4 until
nothing is runnable without the user.

### 1 · Reconcile — evidence first

For every story, recorded state must match evidence; evidence wins, and the files get
corrected when they disagree:

- Phase: `gate-ledger work-get --slug "<story>"`.
- Verdicts: `gate-ledger gate-get --branch "epic/<slug>--<story>"` — a passing verdict
  counts only at that branch's HEAD sha.
- Design doc: the work file's `designDoc` path exists on disk.
- Landed: the story's merge is actually on the epic branch
  (`git -C .studious/worktrees/<slug>/__epic log --oneline`); a story marked `landed`
  without its merge isn't landed.

### 2 · Schedule

Runnable = status `pending` or `running` ∧ every dep `landed` ∧ concurrent stories ≤
the epic's `concurrency`. `parked` and `dropped` stories never schedule; their
dependents wait.

### 3 · Dispatch — one agent, one phase, one story

On a story's first dispatch, create its work file, branch, and worktree:

```bash
gate-ledger work-set --slug "<story>" --title "<story title>" --source "epic:<slug>" \
  --branch "epic/<slug>--<story>" --phase design
git branch "epic/<slug>--<story>" "epic/<slug>"
git worktree add ".studious/worktrees/<slug>/<story>" "epic/<slug>--<story>"
```

Dispatch independent stories' phases in parallel — one message, multiple Task calls.
Each dispatched agent gets its story's context (title, criteria, design doc path,
worktree path) and nothing about other stories. Per phase:

- **design** — a worker agent authors a design doc in the story worktree satisfying
  `reference/design-doc-contract.md`, grounded in PRODUCT.md and the story's acceptance
  criteria. Record it: `gate-ledger work-set --slug "<story>" --design-doc "<path>"`.
- **design-review / audit / acceptance** — run that gate command's workflow as the
  agent, against the story worktree; the gate records its own verdict to the story
  branch's ledger, as always.
- **build** — a worker agent implements the design doc in the story worktree, following
  CLAUDE.md conventions, committing to the story branch. If Superpowers is installed
  the worker uses its plan/execute workflow; otherwise it builds directly.

### 4 · Advance on the verdict

The three-outcome shape in `reference/gate-vocabulary.md` drives every transition; log
each with `gate-ledger work-log --slug "<story>" --step <gate> --outcome "<verdict>"`:

- **Proceed** (`PROCEED TO PLAN`, `PASS`, `SHIP`) → the story's next profiled phase, no
  pause. A `SHIP` at story HEAD → merge: in the `__epic` worktree,
  `git merge --no-ff "epic/<slug>--<story>"`. On conflict, one merge-fixer agent
  attempt in that worktree; still conflicted → `git merge --abort`, park the story with
  reason `merge-conflict`. Merged →
  `gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --status landed` and
  `git worktree remove ".studious/worktrees/<slug>/<story>"` (keep the branch).
- **Fix and retry** (`REVISE`, `FIX AND RE-AUDIT`, `FIX AND RE-CHECK`) → first bump:
  `gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --bump-retry <gate>`.
  If the counter now exceeds 2, park with reason `<gate>: retry cap`. Otherwise
  dispatch a fixer agent with the gate's findings (the fixer never re-runs the gate),
  then re-run the gate with a fresh agent.
- **Judgment** (`RETHINK`, `NEEDS DISCUSSION`, `HOLD`) → park immediately, no retry, no
  workaround: `epic-story-set --status parked --reason "<gate>: <verdict> — <one-line
  gate reasoning>"`. These verdicts exist to reach the user.

## Epic finale

When every story is `landed` or `dropped`, in the `__epic` worktree:

1. `/gate-audit` across the full epic diff (against the merge-base with the default
   branch) — the cross-story integration pass no per-story audit saw.
2. `/gate-acceptance` against the epic goal statement, not any single story.
3. `@agent-premortem-auditor` over the epic pre-mortem register.

Verdicts record to the epic branch's ledger — the PR-time hook reads the same file.
Mechanical failures get the same bounded fix cycle (2, then stop and surface). All
pass → `gate-ledger epic-set --slug "<slug>" --status ready`: recap every story's
verdict trail and remind the user the PR is theirs (`gh pr create` from the epic
branch).

## Skips and amendments

Gate profiles fixed at plan time are the only built-in skip mechanism. Mid-flight,
skip a gate only on the user's explicit say-so — log it
(`work-log --step <gate> --outcome SKIPPED`) and never on your own initiative.

Amendments go through the driver, never hand-edited state: dropping a story →
`epic-story-set --status dropped` (then re-evaluate dependents — a dependent of a
dropped story needs the user to confirm it still makes sense); adding a story → a
scoped plan piece for just that story (a `/gate-should-we-build` pass plus explicit
approval of its DAG placement) before it joins the schedule.

## Close every invocation the same way

End with exactly this shape and nothing after it:

```text
Epic: <slug> — <landed>/<total> landed, <parked> parked, <n> runnable next.
Needs you:
  - <story>: <gate> returned <verdict> — <one clause: what's needed>
Landed this run: <story — verdict trail>
Run /work-through when you're ready, or resolve the queue first.
```

Omit `Needs you:` when nothing is parked. When the epic reaches `ready`, the last line
becomes the `gh pr create` handoff; `stopped` states what ended it. A parked story is
always also a valid `/work-on` feature — say so when the queue is non-empty, so the
user knows they can take any story over by hand.

## Record keeping

All state goes through `gate-ledger` — `epic-set`, `epic-get`, `epic-list`,
`epic-story-set` for the epic; `work-set`, `work-log`, `work-get` for stories;
`gate-get` for verdicts. Never hand-edit or directly read the JSON files. Worktrees
live under `.studious/worktrees/<slug>/` — gitignored, one per running story plus
`__epic`, removed as stories land; `git worktree list` is the recovery tool when state
and disk disagree.
