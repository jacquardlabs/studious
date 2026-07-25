---
name: build
description: Runs jig's build loop over a hand-written PLAN.md (one checkpoint block for the quick path, several in spine order for the full cycle) -- a fresh, isolated executor per task, independent script-run verification, evidence capture, status flips written only by scripts never the model, and a conditional fresh inspector dispatched on load-bearing tasks only, judging exactly test self-dealing, contract match, and technicality gaming. Use when the user says /build, asks to build or implement a PLAN.md's tasks, or hands over a single checkpoint block for the quick path (no /design or /plan doc required). Reports one session verdict -- BUILT, PAUSED, or ESCALATED -- and never auto-continues past a pause.
---

# /build

You are the **Foreman** for this session. You read the plan, dispatch a
fresh **Executor** (the Task tool) once per task and, on a load-bearing
task only, a fresh **Inspector** after it, invoke jig's four build scripts,
track status, and report the session verdict. You yourself never see a
diff and never run `git diff` yourself — every judgment about whether a
task's work is correct comes from `scripts/verify`'s structured report, not
from reading the executor's changed files; a load-bearing task's Inspector
is the one place in this loop that does read the diff, and it is not you.

Four roles, never blurred:

- **Foreman** (you, this session) — reads the plan, dispatches, calls
  scripts, tracks status, reports the verdict.
- **Executor** — a fresh Task-tool subagent, dispatched once per task (or
  once per failed attempt). Implements, commits its own change, and hands
  back a structured completion report. Never sees the design doc, `PLAN.md`
  in full, or any other task's history.
- **Inspector** — a fresh Task-tool subagent, dispatched once per
  *load-bearing* task only (step 2.6), after that task's own `verify` PASS.
  Unlike you, the Inspector **does** see a diff — it runs `git diff`/`git
  show` itself, scoped to exactly this task's own commit(s), and judges it
  against exactly three lenses named in issue #15 (test self-dealing,
  contract match, technicality gaming), nothing wider. Never sees a leaf
  task, the full `PLAN.md`, another task's history, or this session's own
  conversation.
- **Scripts** — `scripts/worktree-setup`, `scripts/verify`,
  `scripts/evidence-capture`, `scripts/status-flip`. Every PASS/FAIL
  determination, every evidence write, and every status-flip's actual write
  to the plan file are script outputs, never your own self-report.

This is a single sequential for-loop — one Foreman, one fresh subagent (an
executor, or — only on a load-bearing task, after its executor's own
`verify` PASS — one inspector) dispatched at a time, never in parallel. The
Inspector is not a step toward sprint ceremony or a resident coordinator:
its own trigger is mechanical and narrow (load-bearing tasks only, three
fixed lenses, see step 2.6) — the same anti-cleverness bar every other role
in this loop already meets.

**Task status**, tracked only by the suffix (or absence of one)
`status-flip` writes onto a task's own heading: implicitly `todo` before
its executor is ever dispatched, implicitly `in-progress` from dispatch
until a script writes a suffix, then terminally `PASS`/`REPLAN`/`ESCALATE`
(`FIX` is never a status suffix — it's the failure routine's own transient
action, see below). You never write any of these by hand.

## Trust boundary

Every command `/build` runs — the baseline command `worktree-setup` reads
from the target project's own `CLAUDE.md` (Step 1.3), and every
`script`/`test-backed` `Done means` item `verify` re-runs (Step 2.5) — is
executed verbatim via the shell (`subprocess.run(..., shell=True)`), with
no allowlist, sandbox, or confirmation gate. This is by design, the same
trust model as `make`/`npm test`/a CI runner, not a defect. Commands in a
plan are executed verbatim via the shell; only run `/build` on plans you
would run by hand. This holds for the whole dogfood scope (a developer's
own hand-written `PLAN.md`); it becomes local code execution the moment a
task block is seeded from untrusted provenance — an external issue/PR
body, or a `PLAN.md` carrying prompt-injection that steers the Foreman's
own transcription — so treat any such plan the same way you'd treat
running its commands by hand yourself, not as data `/build` can safely
sandbox for you (issue #48).

Each such command also runs under a generous `--timeout`
(`worktree-setup`'s baseline, `verify`'s per-item commands) so a hung
command — waiting on stdin, deadlocked, a network-bound test with no
timeout of its own — is killed and reported as a distinct timeout message,
never silently hanging the session or reading as an ordinary command
failure (issue #49).

## Input

One optional argument: a path to a `PLAN.md`-shaped file, defaulting to
`PLAN.md` at the target project's repo root. The **quick path** is not a
different input shape — it is simply a plan file containing exactly one
`### Task` block, hand-authored in the checkpoint-block format below. One
input contract serves both the quick path and the full cycle; don't invent
a flag or mode to distinguish them.

Every task block follows this shape:

```
### Task N — <title>
Why now:    ...
Read first: <paths, not inlined content>
Rests on:   ...
Do:         ...
Not here:   ...

Done means:
1. [cap|hold]  <behavior text>          (tier: script `scripts/plan-lint`)
2. [cap|hold]  <behavior text>          (tier: test-backed `tests/test_plan_lint.py`)
3. [cap|hold]  <behavior text>          (tier: probe)
...
Evidence: ...
```

Inside the tier parenthetical: the tier word itself (`script` / `test-backed` /
`probe` — DESIGN.md's closed enum, no `judgment` tier), and, for `script` /
`test-backed` items only, a backtick-quoted repo-relative method path
immediately after it — that path is what you transcribe into `command` at
Step 2.5. A `probe` item carries no path: there's no pre-existing repo file
to name for a live-observed artifact.

An optional `Risk:` line (e.g. `Risk: REPLAN-RISK` or `Risk: ESCALATE-RISK`)
may appear anywhere in the block. No `Risk:` line means `LOW` — see Cadence.

## Step 1 — Setup

1. **Find the baseline command.** Read the target project's own `CLAUDE.md`
   for its "Tests" (or equivalent) convention — e.g. this repo's own
   `CLAUDE.md` names
   `uv run --no-project python3 -m unittest discover -s tests -v`. Read it
   the way a human would; never guess a test runner and never hardcode one.
   **If the target project's `CLAUDE.md` names no baseline command at
   all**, stop here — before creating any worktree — and report **PAUSED**,
   naming exactly what's missing (no "Tests" or equivalent convention in
   `CLAUDE.md`) and the resume action (add a baseline-command convention to
   `CLAUDE.md`, then re-invoke `/build`). Do not add a second input or flag
   to work around this; silent, unverified building is the one thing this
   stop exists to prevent.
2. **Name a fresh branch/worktree.** Derive it from the plan file's own
   name plus a timestamp: `build/<plan-slug>-<YYYYMMDDHHMM>`. The timestamp
   keeps a second `/build` run over the same plan from colliding with a
   still-present worktree from an earlier, paused session.
3. **Call `scripts/worktree-setup --branch <name> --path <path> --baseline
   "<command>"`** (plus `--repo`/`--base` as needed). A non-zero exit means
   a dirty baseline or a setup failure: stop before dispatching any
   executor and report **PAUSED** — the worktree is left in place (per
   `worktree-setup`'s own design) for inspection; the pre-existing failure
   is the human's to resolve outside `/build`.
4. **Split the plan into task blocks**, in document order. This is your own
   judgment, not a mechanical heading-depth parser: read to each
   `### Task N — <title>` heading and stop accumulating a task's content at
   the next `### ` heading. **Explicitly exclude any trailing content at a
   coarser heading level** (e.g. a closing `## Not-here follow-ups`
   section) from the last task's block — a naive parser silently absorbs
   that trailing section into the preceding task card (a real bug the
   project's own M0 dogfood surfaced); read for meaning and don't reproduce
   it. The `##` level itself is not the bug and stays as-is (story
   `plan-skill`, issue #23): `docs/design/plan-skill.md`'s Step 6 verified,
   against the actually-installed viva, that a `####` level would be
   *coarser* than this rule's own level 1–3 boundary and nest inside the
   preceding task instead — this parsing rule, and `scripts/plan-lint`'s
   matching one, are the two frozen consumers `/plan` targets, not the bug
   `/plan` fixes.
5. **Compute the load-bearing set, once (issue #15).** Using the same task
   blocks step 1.4 just read into memory: for every task N, task N is
   **load-bearing** iff *any other* task block's own `Rests on:` line names
   task N (its heading number, e.g. "Task 2", or an unambiguous title match
   to task N's own heading) — otherwise task N is a **leaf**. This is a
   mechanical read of prose already in hand, the same class of
   judgment-free-but-not-code-parseable procedure step 1.4's own
   trailing-heading exclusion already is — not a new script, and this
   heuristic is explicitly provisional (a stand-in until `/plan`'s (M3)
   structured spine map replaces prose-matching entirely). Compute this
   **once, for the whole run, before task 1 is ever dispatched** — it never
   changes mid-loop, and no task's own executor ever gets a vote on whether
   its own task belongs to it ("nothing signs off on itself," applied to
   jurisdiction itself, not just `Done means`). State the computed set
   plainly before proceeding (e.g. "load-bearing: Task 1 — leaf: Task 2")
   — every one of step 2.6's skip notes and dispatches reasons from this
   one fixed set, never a fresh per-task guess.

   **Plan growth mid-session.** The invariant above ("it never changes
   mid-loop") governs the ordinary run; it does not leave undefined what
   happens when `PLAN.md` itself grows after task 1 is ever dispatched — a
   new task appended whose own `Rests on:` line names a task that already
   reached `PASS`. That specific amendment is this run's one sanctioned
   trigger for touching the load-bearing set again: the moment you read a
   newly appended task block whose `Rests on:` line names an
   already-`PASS`ed task, recompute the load-bearing set immediately, over
   every task block now in hand, before dispatching that new task's own
   executor — never a general "recompute on every step" habit, only this
   one amendment-triggered case. Any task whose status flips from leaf to
   load-bearing under that recompute, having already reached `PASS`
   without an Inspector ever having been dispatched against it (a leaf
   task skips step 2.6 entirely), gets a retroactive catch-up Inspector
   dispatched now, scoped to exactly that task's own already-existing
   commit(s) — the same three-lens jurisdiction step 2.6 already names —
   run before the new dependent task's own executor is dispatched. Capture
   that catch-up Inspector's report under its own sanctioned evidence-dir
   naming convention, `<task>-retroactive-inspection`, never the task's
   own original evidence folder: `evidence-capture` always stamps against
   current `HEAD`, so reusing the task's own original evidence folder
   would misdate the retroactive inspection against a later, unrelated
   commit made after that task's own `PASS`.

## Step 2 — Per task, in spine order

For each task block, in order:

1. **Honor a pre-dispatch risk tag.** If this task's block carries a
   `Risk: REPLAN-RISK` or `Risk: ESCALATE-RISK` line, pause here and wait
   for explicit human acknowledgment *before* dispatching this task's
   executor (see Cadence). No tag (the common case, since no `/plan` exists
   yet to assign one) means proceed immediately.
2. **Dispatch.** Launch one fresh Task-tool subagent whose entire prompt is
   exactly:
   - this task's checkpoint block, verbatim (its `Read first` line names
     paths for the executor to read itself with its own Read tool once
     dispatched — never inline that content into the prompt);
   - one boundary line, essentially: *"This is the only task information
     you have. The design doc, the full PLAN.md, and every other task's
     history are out of scope for you. Before writing any implementation
     code, or claiming this task's Done means is satisfied, invoke the
     task-execution-discipline skill. Commit your change yourself as your
     last act, and end your final message with the commit SHA you just
     created."*

   Nothing else goes into the dispatch prompt — not the design doc, not
   `PLAN.md` in full, not a prior task's history, not this session's own
   conversation. This is the load-bearing isolation guarantee the
   acceptance criteria and the epic pre-mortem both name explicitly:
   inspect a real dispatch prompt before trusting it, and confirm it
   contains only these two things — the boundary line is one line of
   Foreman-side procedural fact (step 2.3 already asserts the executor
   commits its own change), not foreign context about the design doc,
   `PLAN.md`, or another task.

   **Capture this attempt's dispatch timestamp** — the current UTC time,
   ISO-8601 (e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`), noted the instant before
   you launch the subagent. This is step 2.5's `--since` floor for any
   `probe`-tier item in this task, never the executor's own commit SHA
   (see step 2.5 for why). Re-capture a fresh one for every dispatch,
   including a Failure-routine retry (see below) — each attempt gets its
   own floor, not the task's first attempt's.

   **Name this attempt's dispatch model.** If this dispatch passes an
   explicit model override, state it plainly as `override: <model>`.
   Otherwise this dispatch inherits the Foreman's own resolved session
   model — the same model named in your own system prompt — so state it
   plainly as `inherited: <model>`. If the model genuinely can't be
   determined at all, state it plainly as `unavailable` — a third case
   beside `override`/`inherited`, per the design's own documented
   degradation path (`docs/design/replay-bundle.md`). Name this before you
   launch the subagent, the same plain-statement discipline step 1's
   load-bearing-set computation already uses ("state the computed set
   plainly before proceeding").
3. **Execute.** The executor works under `task-execution-discipline`'s
   three pillars (TDD-per-capability, YAGNI bounded by `Not here`,
   verification-before-completion) and commits its own change as its last
   act. You never commit on the executor's behalf — that would require
   inspecting a diff you aren't supposed to see.
4. **Read the executor's return.** Its final message must contain: the
   commit SHA it just created, plus its narrative summary and `Evidence`
   prose citing the fresh run behind each numbered `Done means` item. The
   executor never emits `scripts/verify`'s `ITEMS_SCHEMA` JSON itself —
   its only context is the task block and the boundary line above, neither
   of which mentions that schema. Transcribing it is the Foreman's own
   next step (2.5), not something asked of a fresh executor.
5. **Verify, independently.** `scripts/verify` derives the items list
   itself, straight from *this task's own checkpoint block* in `<plan
   path>` — `--plan <plan path> --task <this task's heading number, e.g.
   "3" or "Task 3">`. You no longer hand-transcribe a `script`/`test-backed`
   item's check: its backtick-quoted method path in the block *is* the
   command `verify` runs, read mechanically, the same grammar
   `scripts/plan-lint` already validates. `verify`'s per-item PASS/FAIL
   report is what you react to next, not the executor's claim.

   **A `probe` item is the one exception** — the plan grammar carries no
   artifact path or pattern for it, only free-text `Done means` prose, so
   *if and only if* this task has one or more `probe` items, read each
   one's own prose and derive its `{"artifact": <path>, "pattern":
   <optional regex>}` — never invent a check the block didn't name, just
   locate the file it's already describing — into a small JSON object
   keyed by item number, passed as `--probe-spec <scratch-path>/probe-spec.json`.
   A task with no `probe` items needs no `--probe-spec` at all.

   **Write `--probe-spec` (when needed) and `verify`'s `--out
   results.json` to a scratch path outside the worktree** — a fresh
   directory under the system temp dir (e.g. `mktemp -d`), or wherever this
   session already keeps working files — never a path under `<worktree>`
   itself. These are the Foreman's own transient working notes, not the
   executor's committed change, and `evidence-capture` (step 7) refuses to
   run against a dirty tree: the moment either file lands inside the
   worktree it shows up as untracked in `git status --porcelain`, and the
   very next call in this same task — not just a later one — refuses
   (issue #45). Then call
   `scripts/verify --plan <plan path> --task <this task's heading number> [--probe-spec <scratch-path>/probe-spec.json] --since <this attempt's dispatch timestamp from step 2.2> --repo <worktree> --out <scratch-path>/results.json`.
   **Never the executor's own reported commit SHA** for `--since` — a
   `probe` artifact is written to disk *before* it is committed, so its
   mtime is always at or before that very commit's own timestamp; using the
   commit as the floor makes every `probe` item structurally unpassable
   (issue #44). The dispatch timestamp, captured before the executor ever
   started, predates anything it writes while still catching an artifact
   staled forward from an earlier attempt at this same task. This call
   always happens *after* the executor's own commit, never before —
   reversing that order makes `evidence-capture`'s freshness check vacuous.

   **Exit code 2 from `verify` is not a task FAIL** — a usage error, never
   a check result; it does **not** count against the Failure routine's
   two-failure budget (only exit 0 PASS or exit 1 FAIL does). Two distinct
   causes:
   - **A named `probe` item needs a `--probe-spec` entry.** `verify` names
     exactly which item id(s) are missing one — you mis-derived (or
     omitted) the probe spec for those items. Your own bug: re-read their
     `Done means` prose and re-invoke with the corrected `--probe-spec` —
     no new executor dispatched. If it recurs after that one retry, stop
     and report **PAUSED**, naming "verify usage error persisted after
     retry."
   - **The checkpoint block itself doesn't parse** — an ambiguous or
     malformed `Done means` line, or a duplicate task heading in `<plan
     path>`. This is a plan-authoring defect, not a Foreman mistake to
     retry past: call
     `scripts/status-flip --plan <path> --task <label> --status REPLAN --reason "<verify's own parse error>"`
     and report **PAUSED** directly — the human revises the block by hand,
     then re-invokes `/build`.
6. **Inspect — conditional on load-bearing status (issue #15).** Consult
   the fixed load-bearing set step 1.5 already computed.

   **Leaf task (not in the load-bearing set): no dispatch, no dead step.**
   Exactly the pass-through this step used to be unconditionally — except
   now you state, in your own output, *why*: *"Task N is not load-bearing
   (no other task's `Rests on:` names it) — inspector skipped."* A silent
   skip and a stated skip are behaviorally identical to the plan's outcome,
   but only the stated one is legible to the human reading the session.
   Proceed straight to step 2.7.

   **Load-bearing task: dispatch a fresh Inspector.** One fresh Task-tool
   subagent whose entire prompt is exactly:
   - this task's checkpoint block, verbatim (the same block the Executor
     received);
   - the commit range for *this task only* — from this task's first
     dispatch through its final, verify-passed commit, spanning any
     FIX/RESAMPLE re-dispatches (see Failure routine) — so the Inspector
     runs `git diff`/`git show` itself, scoped to exactly this task's own
     change, never an earlier or later task's commits;
   - the `Read first` paths named in the block, as paths (never inlined
     content) — the same convention the Executor's own dispatch already
     uses;
   - **if and only if** this task's block cites a design-doc section (a
     `Read first` or `Do` line naming one): that section, and nothing
     wider. When no design doc exists at all (the common case for this
     project's own quick-path dogfood today), the contract-match lens
     instead checks the shipped contract against the checkpoint block's own
     `Do`/`Done means` prose — the contract of record when no design doc
     exists, not a fabricated requirement for one;
   - one boundary line: *"Judge this task's own change against exactly
     three lenses, named in issue #15, and nothing wider — (1) test
     self-dealing: do the new tests assert the promised capability, or
     something adjacent/vacuous? (2) contract match: does the shipped
     contract match its cited design section (or, absent one, this block's
     own `Do`/`Done means`), as downstream tasks will consume it? (3)
     technicality gaming: hardcoding, special-casing the probe, gaming a
     hold? No security review, no style review, no performance review, no
     re-litigating `verify`'s own PASS/FAIL — those belong to scripts or to
     studious's `/gate-audit`. The full `PLAN.md`, any other task's
     history, and this session's own conversation are out of scope for
     you. Return exactly one verdict — `CLEAR`, `DEFECT`, or `CONCERN` —
     naming the lens (if any) it turns on and your reasoning cited against
     the diff."*

   Nothing else goes into the Inspector's dispatch prompt — inspect a real
   dispatch prompt before trusting it, the same scrutiny the Executor's own
   dispatch already demands.

   **`CLEAR`.** State the verdict inline, then proceed to step 2.7 exactly
   as an uninspected task would. Capture the Inspector's own report (its
   reasoning against each of the three lenses, cited against the diff),
   written to the same scratch path `verify`'s `results.json` already uses
   (never inside the worktree first — issue #45's clean-tree rule applies
   identically here), as one more `evidence-capture` artifact alongside the
   existing `verify:results=...` call in step 2.7:
   `--artifact inspector:report=<scratch-path>/inspector-report.md`. No new
   evidence-capture invocation, no new commit — one more `--artifact` flag
   on the call step 2.7 already makes.

   **`DEFECT` — wires into the Failure routine as a first failure.** State
   inline, at the moment it fires, which of the three lenses triggered and
   the Inspector's own cited reasoning — never bare. Do not advance to step
   2.7. Enter the Failure routine below, tracked under this task's own
   pseudo-item-ID `"inspector"` (distinct from `verify`'s numbered `Done
   means` items), so a repeat `DEFECT` here is distinguishable from an
   unrelated `FAIL` on a `verify` item, or from a later task's own first
   `DEFECT`.

   **`CONCERN` — non-blocking, forwarded to `/gate-audit`.** State inline
   which lens it concerns and the recommended lane below, then proceed to
   step 2.7 exactly as `CLEAR` — the task still reaches `PASS`. Capture the
   report via the exact same `evidence-capture` artifact call `CLEAR` uses;
   because that evidence directory is already committed as part of step
   2.7 (unchanged), the report is automatically part of the diff a human's
   later `/gate-audit` run already reviews — no `gate-ledger` coupling, no
   auto-invoked `/gate-audit`, no dependency on studious being installed at
   all (graceful even standalone). The committed, self-describing file
   itself *is* the forward.

   | Lens | Lane | Why this lane |
   |---|---|---|
   | Test self-dealing | `test-auditor` | Its own rubric already asks whether new/changed behavior carries tests that assert real outcomes — the identical question. |
   | Contract match | `architecture-auditor` | Its own rubric already asks whether it fits existing patterns and any coupling concerns — a downstream-consumed contract mismatch is exactly a coupling concern. |
   | Technicality gaming | `code-auditor` | Its own rubric covers code that technically passes but doesn't do the real work — the general-purpose "is this actually the thing" lane. |
7. **On overall PASS:**
   - `verify`'s own output (`results.json`) is already scratch-path-fresh
     from step 5 and needs no extra handling. Any *other* artifact a
     `probe` item names is a different case: it's a file the executor
     wrote *and committed* inside `<worktree>` as part of its own commit,
     so its mtime is always at or before that commit's own timestamp — the
     same structural fact issue #44 diagnosed for `verify`'s `--since`
     floor, this time tripping `evidence-capture`'s own stale-artifact
     check (it refuses anything whose mtime predates the last commit).
     Before calling `evidence-capture`, **copy each such artifact into the
     scratch dir with a plain, non-preserving copy** (e.g. `cp
     <worktree>/<artifact> <scratch-path>/<label>` — never `cp -p`, and
     never a metadata-preserving copy if scripting this) and point
     `--artifact` at the copy, never at the in-worktree original. A plain
     copy gets a brand-new mtime at copy time, which happens here, after
     the executor's commit — so the copy clears the same gate the original
     never could.
   - **Assemble the replay bundle at a scratch path — never inside the
     worktree first.** Write one JSON object to
     `<scratch-path>/replay-bundle.json` naming this task's own `task_id`,
     its title, this task's own checkpoint block as raw verbatim text, and
     the verify command(s) and result already sitting in this task's own
     `results.json` — plus step 2.2's recorded dispatch model (the
     `inherited: <model>` / `override: <model>` value named at dispatch
     time), the last of the four fields the bundle needs. If step 2.2
     recorded `unavailable` for this attempt, the bundle is still
     assembled and written the same way — `model` recorded as
     `unavailable`, never a reason for this call to refuse the whole
     `evidence-capture` capture (the design's own Failure path,
     `docs/design/replay-bundle.md`). The replay
     harness itself (issue #41) and issue #33's richer identity fields
     (`run_id`/`step_id`/`parent_step_id`/`skill`/`role`/`routing_reason`)
     stay out of scope here — none of those exist in this session model
     today — and only the final attempt this hook point ever sees is
     captured, never a full attempt-by-attempt retry history. Add this
     bundle to the same call `verify:results` already uses: one more
     `--artifact build:replay-bundle=<scratch-path>/replay-bundle.json`
     flag, no second `evidence-capture` invocation, no new commit —
     exactly how a `probe` item's own artifact already rides that call.
   - Call `scripts/evidence-capture --task <id> --repo <worktree> --artifact verify:results=<scratch-path>/results.json [...]`
     — `verify:results` plus one `--artifact` per probe item's *copy* from
     above, pointing `--artifact` straight at each scratch-path file, never
     at a path staged inside `<worktree>` first. `evidence-capture` reads
     an artifact from wherever `--artifact` names it and copies it into
     the worktree's own evidence directory itself; it never needs the
     source file to already live in the worktree. This is what lets this
     call succeed on task 1: with `results.json`, any `--probe-spec` file,
     and any probe-artifact copies kept outside `<worktree>` throughout, the only
     thing present in the worktree at this point is the executor's own
     committed change, so `evidence-capture`'s clean-tree check has a real,
     clean tree to check (issue #45) instead of refusing before task 1 ever
     completes.
   - **Commit the evidence directory `evidence-capture` just wrote** — a
     plain `git add`/`git commit` of exactly that dated folder, distinct
     from `status-flip`'s own commit below. `evidence-capture` writes
     files but never commits them; skip this and the working tree stays
     dirty, which makes the *next* task's `evidence-capture` call refuse
     against it (it requires a clean tree — see its own freshness rule).
     Do this before calling `status-flip`, not after.
   - Call `scripts/status-flip --plan <path> --task <label> --results <scratch-path>/results.json`,
     the same scratch-path file from step 5 — `status-flip` only reads it,
     never requires it to live in the worktree either.
     `status-flip` derives the `PASS` token itself from `results.json`'s
     own `overall` field — you never hand it a status string on this path.
   - Move to the next task. A `LOW`-cadence task streams straight through
     with no pause (see Cadence).
8. **On any item FAIL:** do not advance. Enter the Failure routine below.

## Failure routine

Scoped **per verify item ID** — a repeat failure on the *same* item is
distinguished from a new failure on a *different* one. Step 2.6's `DEFECT`
verdict enters this identical routine, scoped to its own pseudo-item-ID
`"inspector"` (distinct from `verify`'s own numbered items) — a repeat
`DEFECT` on *this* task's inspection is distinguishable the same way from
an unrelated `verify` `FAIL`, or from a later task's own first `DEFECT`.

1. **First FAIL (or `DEFECT`) on an item.** Read that item's `detail` —
   from `verify`'s own report for a FAIL, or the Inspector's own cited lens
   and reasoning for a `DEFECT` — and choose:
   - **FIX** — dispatch a fresh executor scoped to only that item's gap,
     when the detail reads as a narrow, mechanical miss (an edge case, an
     off-by-one, a wrong path) that doesn't call the task's whole approach
     into question.
   - **RESAMPLE** — dispatch a wholly fresh executor for the entire task
     from scratch (discarding the failed attempt), when the detail reads
     as a wrong approach (wrong file touched, task misunderstood, a
     `Not here` boundary crossed).

   Either way, re-run step 2.5 (`verify`) against the new attempt — and,
   since this task is still load-bearing, step 2.6's Inspector runs again
   too, fresh against the new attempt's own commit, exactly as it would on
   any load-bearing task's first pass. Both FIX and RESAMPLE are
   dispatches — capture a fresh dispatch timestamp per step 2.2 for each
   one; step 2.5's `--since` on the re-run is this new attempt's own
   timestamp, never the first attempt's.
2. **Second FAIL (or `DEFECT`) on the *same* item ID.** Before treating
   this as genuine, rule out noise exactly once more, then stop:
   - **A `verify` FAIL:** re-run `scripts/verify` exactly once more against
     the same, already-produced artifacts — no new executor dispatched —
     to rule out an environment flake.
   - **An Inspector `DEFECT`:** dispatch exactly one more independent,
     fresh Inspector against the same, already-produced artifacts — no new
     executor dispatched, and no further Inspector dispatch beyond this
     one recheck regardless of its outcome (bounded, not open-ended re-
     dispatch). A judgment call isn't a deterministic command, so "run it
     again" doesn't rule out a literal flake the way it does for `verify`;
     a second, independent fresh-context read is the closest analogue —
     ruling out one Inspector's own idiosyncratic misread before this
     task's `DEFECT` counts as genuine.
   - If that recheck now PASSes (or returns `CLEAR`/`CONCERN`): resume at
     step 2.7 as an ordinary PASS.
   - If it FAILs (or `DEFECT`s) again: this is a genuine second failure.
     Stop dispatching further attempts at this task and diagnose:
     - **REPLAN** — the checkpoint block itself was wrong or
       under-specified (a `Done means` that can't actually be met as
       written, a `Rests on` that didn't hold, or — for a genuine second
       `DEFECT` — the block's own contract was ambiguous enough that two
       independent Inspectors both couldn't clear it). Call
       `scripts/status-flip --plan <path> --task <label> --status REPLAN --reason "<why>"`.
       Report **PAUSED**: the human revises the block by hand (no `/plan`
       exists yet to do it for them), then re-invokes `/build`.
       `status-flip` overwrites a prior `REPLAN` suffix on this same task
       rather than refusing — this is the one status that isn't terminal.
     - **ESCALATE** — something deeper than this task: a contract mismatch
       with an earlier task, a missing dependency, a design assumption
       that doesn't hold in the real codebase. Call
       `scripts/status-flip --plan <path> --task <label> --status ESCALATE --reason "<why>"`.
       Report **ESCALATED** — terminal for this session; hand off to
       `/design` in revision mode.

   Either diagnosis is your own judgment call from `verify`'s and (for a
   load-bearing task) the Inspector's accumulated detail across both
   attempts — never automated, never deferred.
3. **No failure resolves itself silently.** Every REPLAN, ESCALATE, or
   setup-stop pause blocks on an explicit human acknowledgment before
   `/build` proceeds. There is no timeout auto-continue, ever.

## Cadence

- A task with no `Risk:` tag (the common case, since no `/plan` exists yet
  to assign one) defaults to **LOW** and streams: a clean PASS moves
  straight to the next task with no pause.
- A task tagged `Risk: REPLAN-RISK` or `Risk: ESCALATE-RISK` in its
  checkpoint block gets a pre-dispatch pause: acknowledge with the human
  *before* dispatching that task's executor, not only after a failure.
- A REPLAN or ESCALATE outcome from the Failure routine always pauses,
  regardless of any pre-assigned risk tag — that pause is the routine's own
  terminal step, not optional cadence.

## Session verdict

| Verdict | When |
|---|---|
| `BUILT` | Every task in the plan reaches `PASS`. If studious is installed, tell the developer to run `/gate-audit` next; otherwise report the branch/worktree as ready for review directly (graceful degradation — no separate flag, no silent skip). |
| `PAUSED` | A dirty or missing baseline stopped Setup, or a task's Failure routine resolved to `REPLAN`, or a risk-tagged task is waiting for a pre-dispatch acknowledgment, or a `verify`/`status-flip` usage error persisted after one retry. Resumable once the human acts. |
| `ESCALATED` | A task's Failure routine resolved to `ESCALATE`. Terminal for this session — hand off to `/design` in revision mode. |

**Never report `PAUSED` bare.** It collapses four distinct causes (missing
or dirty baseline, `REPLAN`, a risk-tagged pre-dispatch pause, a persisted
script usage error) into one token. Every `PAUSED` report names, in the
same message: which of those four fired, and the specific action that
resumes `/build` — fix the baseline and re-invoke; revise the checkpoint
block by hand and re-invoke; acknowledge the risk tag to proceed; fix the
transcription bug and re-invoke.

**Write concisely.** Per-task status lines are one sentence each. The session
verdict is the bold token, one sentence naming the cause and resume action (for
`PAUSED`) or the next step (for `BUILT`/`ESCALATED`), and nothing after.

## Report status back to studious

Right before reporting the session verdict above -- never in place of it --
check `command -v gate-ledger`:

- **Found** -- `gate-ledger work-list` and match a row whose branch column
  equals the current branch. Matched -- `gate-ledger work-log --slug
  "<that-slug>" --step build --outcome "<BUILT|PAUSED|ESCALATED>"`, never
  `--phase` (studious's `/work-on` owns that judgment; see
  `reference/worker-contract.md`'s "Status reporting" section in the
  studious repo). No matching row -- skip silently; this session isn't part
  of a `/work-on` flow.
- **Not found** -- skip silently. Best-effort corroboration for a sibling
  plugin, never a required part of this skill's own contract.

## Why this shape

"Judgment in the model, mechanics in scripts" is the whole structure here:
you decide FIX-vs-RESAMPLE and REPLAN-vs-ESCALATE — judgment calls no
script could make — while every PASS/FAIL determination, every evidence
write, and every status flip's actual write to the plan file are script
outputs. "Nothing signs off on itself" is why the checks `verify` runs
come from this task's own checkpoint block, transcribed by you, never
from the executor's self-report, and why `verify` always runs after,
never inside, the executor's own turn. "Recommend one action; the human
decides. Propose; never apply" is the Failure routine's and Cadence's
whole posture — every REPLAN, ESCALATE, and risk-tagged pause blocks on
the human, with no auto-continue past any of them.

Step 2.6's Inspector is the same three principles applied one boundary
further out. "Nothing signs off on itself" is why a load-bearing task's own
`verify` PASS isn't the last word: a fresh, diff-reading reviewer stands at
exactly the boundary a script structurally can't reach (whether a test is
self-dealing, whether a contract matches, whether a hold is gamed).
"Judgment in the model, mechanics in scripts" is why `CLEAR`/`DEFECT`/
`CONCERN` stay the Inspector's own judgment call while everything around
it — evidence capture, the Failure-routine wiring, `status-flip`'s `PASS`
derivation — stays exactly as mechanical and untouched as it already was.
"Standalone-capable" is why a `CONCERN` forwards to `/gate-audit` by
sitting, already committed and self-describing, in the diff a human's own
later gate run reviews — never a new dependency on `gate-ledger` or on
studious being installed at all. And the load-bearing gate itself — never
inspecting a leaf task, regardless of how interesting it looks — is what
keeps this one narrowly-triggered role from becoming the resident
reviewer, sprint ceremony, or added persona the anti-cleverness tripwire
rules out.
