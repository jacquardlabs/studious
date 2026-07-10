---
description: Drive a whole milestone or epic through the gate flow with dispatched agents — plan once for approval, then run everything runnable, stopping only for judgment calls
argument-hint: "[milestone, epic issue, or label] (omit to keep driving the epic in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Workflow
---

# Work through an epic

Drive a whole milestone through the same gate flow `/work-on` walks one piece at a
time. This command owns state assembly and reporting; a deterministic Workflow script
owns scheduling (which stories run, in what order, retry caps, merge order); dispatched
agents own every judgment. Code owns bookkeeping; prompts own judgment. Two modes,
resolved by state rather than flags: no epic in flight → the plan piece; an approved
epic → the driver.

**The posture — non-negotiable:**

- **Gates are unbypassable.** Gate agents run the gate commands' workflows verbatim;
  never soften, reinterpret, or skip a verdict. Tokens are canonical in
  `reference/gate-vocabulary.md`.
- **Lanes stay separate.** Gate agents never build; worker agents never gate
  (`reference/worker-contract.md`); the two never share context. A gate judges the
  diff and the doc, never a worker's transcript.
- **GitHub is read-only.** Never create or edit issues; never open PRs — after the
  finale the branch is the user's (`gh pr create`).
- **Judgment verdicts always stop the story** and wait for the user. Autonomy never
  absorbs a RETHINK, NEEDS DISCUSSION, or HOLD; unknown verdicts park too, never
  advance.
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
   - Create the integration branch **from the default branch — never from whatever
     happens to be checked out** — and give it its own worktree, leaving the user's
     checkout untouched:

     ```bash
     default=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
     git branch "epic/<slug>" "${default:-main}"
     git worktree add ".studious/worktrees/<slug>/__epic" "epic/<slug>"
     ```

5. Close with the report block below. Driving starts on the next invocation — approval
   and execution never share one.

## Driver — every later invocation

If the epic's status is still `approved`, mark the run started:
`gate-ledger epic-set --slug "<slug>" --status running`.

### 1 · Reconcile — evidence first

Recorded state must match evidence before anything is dispatched; evidence wins, and
the files get corrected (via `gate-ledger`, never by hand) when they disagree:

- Epic and stories: `gate-ledger epic-get --slug "<slug>"`; per-story phase:
  `gate-ledger work-get --slug "<story>"`.
- Verdicts: `gate-ledger gate-get --branch "epic/<slug>--<story>"` — a passing verdict
  counts only at that branch's HEAD sha.
- Design docs: each recorded `designDoc` path exists in its story worktree.
- Landed: the story's merge is actually on the epic branch
  (`git -C .studious/worktrees/<slug>/__epic log --oneline`); a story marked `landed`
  without its merge isn't landed.

From the reconciled state, derive each unfinished story's **next phase** (first phase
in its gate profile whose evidence is missing). One special value: if every profiled
gate has already proceeded at the story branch's HEAD and only the merge onto the epic
branch is missing, the next phase is the sentinel `merge` — the script jumps straight
to landing the story instead of re-running its profile.

### 2 · Run the driver script (primary mode)

The scheduler is code, not prose. Resolve the plugin root (the plugin's `bin/` is on
`PATH`, so the ledger's location reveals it):

```bash
plugin_root="$(cd "$(dirname "$(command -v gate-ledger)")/.." && pwd)"
# driver script: $plugin_root/workflows/epic-driver.js
```

Read `${plugin_root}/reference/prompt-contract.md` once (the same plugin-root
resolution the four gate commands use; if it isn't there, locate
`reference/prompt-contract.md` inside the plugin install with Glob — never guess a
path or skip this read). The script has no hands to read a file itself: hand it the
four blocks — the injection-defense preamble, the read-only/diff-scope convention, the
output-row schema, and the calibrate-don't-suppress closer — verbatim as
`args.contract`, so it can stamp them into every audit and premortem dispatch it
builds, per-story and at the finale, exactly as the four gate commands stamp them into
their own Task dispatches. This is the whole handoff — no runtime-pointer resolution
happens on this path. The script fails closed at any dispatch that needed the contract
if it arrives empty or missing, so treat a missing file here as a stop, not a skip.

Call the Workflow tool with `scriptPath` set to that file and `args`:

```json
{
  "epic": "<the epic-get JSON, verbatim>",
  "phases": { "<story>": "<next phase>" },
  "repoRoot": "<absolute path of the main working tree>",
  "defaultBranch": "<resolved default branch>",
  "contract": "<reference/prompt-contract.md's four blocks, verbatim>",
  "timestamp": "<current ISO time>"
}
```

The script schedules the DAG under the concurrency cap, dispatches workers
(`reference/worker-contract.md`) and gates, applies the verdict rules mechanically
(fix-and-retry verdicts: fixer + fresh-eyes gate re-run, capped; judgment verdicts:
park immediately), merges each story when its **final profiled gate** returns its
proceed token, and runs the epic finale when everything has landed or been dropped.
Every state mutation is written by the agent that caused it, via `gate-ledger` — the
script's memory is a working copy, so a killed run resumes by re-running this command:
reconcile, re-invoke, nothing duplicated or lost.

Render the script's return value in the fixed report shape below. Do not re-derive or
second-guess its scheduling; anything it parked is the user's, not yours to retry.

### Fallback driver — use only when the Workflow tool is unavailable

Semantics are identical to the script's (defined once in the design doc; the two modes
are interchangeable mid-epic): walk each runnable story's next phase with dispatched
agents — runnable = every dependency `landed` ∧ not `parked`/`dropped` ∧ under the
epic's cap — dispatching independent stories in parallel (one message, multiple Task
calls). Workers follow `reference/worker-contract.md`; gate agents run the gate
command workflows and record their own verdicts from inside the story worktree.
Design-review and acceptance need no extra step — the single dispatched agent reads
its gate command and self-injects exactly as it would from the script path. Audit is
different here too: read `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md`
yourself (same anchored resolution, Glob fallback if it doesn't substitute) and stamp
its four blocks into every audit and premortem Task prompt you dispatch in this
mode — you are the assembly point on this path exactly as your own read is on the
script path. Log every step with
`gate-ledger work-log --slug "<story>" --step <phase> --outcome "<token>" --phase "<next phase>"`.
Apply verdicts exactly as the script does:

- **Proceed** → the story's next profiled phase; when the **final profiled gate**
  proceeds at story HEAD (SHIP for a full profile; whatever its last gate's proceed
  token is for a trimmed one), merge in the `__epic` worktree (`git merge --no-ff`,
  one merge-fix attempt, abort → park), then
  `epic-story-set --epic "<slug>" --slug "<story>" --status landed` and
  `git worktree remove ".studious/worktrees/<slug>/<story>"` (keep the branch).
- **Fix and retry** → `epic-story-set --epic "<slug>" --slug "<story>" --bump-retry
  <gate>`; park once the recorded counter exceeds 2; otherwise a fixer agent (never
  re-runs the gate), then a fresh gate agent.
- **Judgment or unknown** → park immediately:
  `epic-story-set --status parked --reason "<gate>: <verdict> — <one clause>"`.

## Epic finale

When every story is `landed` or `dropped` (the script runs this itself; in fallback
mode, run it in the `__epic` worktree):

1. The audit fan-out across the full epic diff (against the merge-base with the
   default branch) — the cross-story integration pass no per-story audit saw.
2. `/gate-acceptance` against the epic goal statement, not any single story.
3. `@agent-premortem-auditor` over the epic pre-mortem register.

Verdicts record to the epic branch's ledger — the PR-time hook reads the same file.
All pass → `gate-ledger epic-set --slug "<slug>" --status ready`, then release the
integration checkout so the branch is checkoutable from the user's clone:
`git worktree remove ".studious/worktrees/<slug>/__epic"`. Recap every story's verdict
trail and remind the user the PR is theirs (`gh pr create` from the epic branch).

## Skips, amendments, and un-parking

Gate profiles fixed at plan time are the only built-in skip mechanism. Mid-flight,
skip a gate only on the user's explicit say-so — log it
(`work-log --step <gate> --outcome SKIPPED`) and never on your own initiative.

Amendments go through this command, never hand-edited state:

- **Un-park** — the driver never un-parks on its own. When the user resolves a parked
  story (answers the question, revises the design, accepts a risk), record it so the
  next run schedules the story with fresh fix cycles:

  ```bash
  gate-ledger epic-story-set --epic "<slug>" --slug "<story>" \
    --status pending --reason "resolved: <one clause>" --reset-retry <gate>
  ```

- **Drop** — `epic-story-set --status dropped`, remove the story's worktree if one
  exists, then re-evaluate dependents: a dependent of a dropped story needs the user
  to confirm it still makes sense.
- **Add** — a scoped plan piece for just that story (a `/gate-should-we-build` pass
  plus explicit approval of its DAG placement) before it joins the schedule.

## Close every invocation the same way

End with exactly this shape and nothing after it:

```text
Epic: <slug> — <landed>/<total> landed, <parked> parked, <blocked> blocked on them.
Needs you:
  - <story>: <gate> returned <verdict> — <one clause: what's needed>
Landed this run: <story — verdict trail>
Run /work-through when you're ready, or resolve the queue first.
```

Omit `Needs you:` when nothing is parked. When the epic reaches `ready`, the last line
becomes the `gh pr create` handoff; `stopped` states what ended it. A parked story is
always also a valid `/work-on` feature — say so when the queue is non-empty; taking a
story over by hand happens inside its worktree (the story branch is checked out
there), or after `git worktree remove` on it.

## Record keeping

All state goes through `gate-ledger` — `epic-set`, `epic-get`, `epic-list`,
`epic-story-set` for the epic; `work-set`, `work-log`, `work-get` for stories;
`gate-get` for verdicts. State lives in the MAIN working tree's `.studious/` no matter
which worktree an agent writes from — the ledger anchors there itself. Never hand-edit
or directly read the JSON files. Worktrees live under `.studious/worktrees/<slug>/` —
gitignored, one per running story plus `__epic`, removed as stories land and at
`ready`; `git worktree list` is the recovery tool when state and disk disagree.
