---
description: The standup question at any scale — where is this, and what now. Reads position from recorded state and repo evidence, names the next door, and runs it on your word. One story, a list, or a whole milestone. Use for "what's next", "do the next piece", "where am I", "keep going", "drive this milestone", "knock out this milestone", "run the whole epic", "build issue 12", "take this through the flow". Do NOT use for picking what to work on (that's /bet), for running a specific review (that's /review), or for a periodic project sweep (that's /health).
argument-hint: "[idea, issue, milestone, or in-flight work] (omit to continue what's in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Workflow
---

# What's next

One door for "where am I, what now" — at story, list, or milestone scale. The flow is
scale-invariant: the same doors in the same order regardless of size. Scope changes how many
stories a bet contains and how much runs dispatched versus supervised; it never changes which
doors exist.

This door judges nothing and builds nothing. It reads position, names the next door, and
runs it on your word. Verdicts belong to `/review`; commits belong to `/build` and `/ship`.

Read PRODUCT.md at the project root first.

## Report first, run on confirmation

**Default: report, then ask.** Say where the work stands, name the next door and what it
involves, and stop for the user's word before running it. Propose, don't apply.

**One exception:** if the previous turn's closing block already named this exact piece and
the user's message is an advance ("next", "go", "keep going", a bare `/next`), that *is*
the confirmation — run it without asking again.

**A second exception, epic scale only (#311):** a recorded viva sign-off on a brief
satisfying every element in `reference/epic-plan-contract.md` IS the user's word for that
plan. It approves only the plan it was stamped against; it never licenses auto-advance
past the piece that plan authorizes — "Never auto-advance past the piece you ran" below
still governs everything after. A brief missing any required element is
rejected at intake — never approved by default, never inferred.

**Never auto-advance past the piece you ran.** When it finishes — pass, fail, or handoff —
stop with the closing block below, even when the result is a clean pass and the next step is
obvious. The user advances the flow; you never do.

**A piece runs to its next real decision without asking (#371).** Inside a piece — and
inside a `story-supervised` story under an epic — never pause to ask "run it now?", "pick
up the next task?", or "ready when you are". `story-supervised` means the human is
*present* for the class of work (`reference/epic-plan-contract.md`), not that each step
needs a fresh go. The stops are the decisions this door already names — a stop/rethink
token, a Critical waiver, a round cap, a fork, a sign-off, the ship verdict, appetite — plus
`PAUSED`/park with a named cause. Everything else is a report line, not a question. Measure:
human turns per supervised story ≤ decisions made (`scripts/retro-stats` counts both).

**One deliberate exception, inside a piece rather than between pieces.** Pieces 2 (design)
and 3 (build) each used to be two pieces — a handoff, then a separate `/review` this door
ran once the handoff's output existed — and each pair required its own confirmation to
cross. `/shape` and `/build` now convene their own review episode at exit
(`reference/personas.md`, "producer... may *convene* a judge"), so that boundary is no
longer a separate door invocation for this door to stop between: running `/shape` or
`/build` now means reading back its own verdict *and* the episode it convened, in one
report, from one piece. This door still stops with the closing block after every piece in
the table below, on every verdict, clean or not — that principle is unchanged. What
changed is only what a "piece" now spans.

**When recorded state and the repo disagree, stop and name the disagreement.** Do not guess
or quietly pick one. Evidence usually wins (see below), but a contradiction the evidence
rules can't settle is a question for the user.

## The flow

| # | Piece | Door | Done when |
|---|-------|------|-----------|
| 1 | bet | `/bet` | verdict recorded (**BUILD** / **BUILD SMALLER** continue) |
| 2 | design | `/shape` (convenes `/review`) | **PROCEED TO PLAN** closes the design episode |
| 3 | build | `/build` (convenes `/review`) | **PASS** closes the work episode |
| 4 | delivery review | `/review --delivery` | **SHIP** closes the delivery episode |
| 5 | ship | handoff | branch closed out: scaffolding removed, evidence assembled, PR opened or work merged/parked |

Piece 5 is a pure handoff — closeout, the one step with no judge behind it. Pieces 2 and 3
hand off writing (the design, the code) exactly as before, but no longer hand off judging
it separately: `/shape` and `/build` convene their own episode when they're the route
used (see the exception above). Either route is still the user's pick — a hand-written
spec, or Superpowers' brainstorming/planning (or plan/execute) workflow, reaches the same
episode through this door running `/review` directly instead, exactly as this door always
has; no episode cares which route produced the branch.

After piece 5 the flow is `done`. Never open the PR yourself: the PR is the user's
(`gh pr create` — the PR-time hook reads the same ledger). This is a story-scale rule.
At epic scale the finale itself opens the epic's PR, once, after its gates pass
(`reference/epic-orchestration.md`, "Epic finale") — that is not this door acting; see
the closing-shape note below.

No door is mandatory, only default. Skipping `/bet` means no appetite and no decision record
exist — position still derives from repo evidence, and every later door runs regardless.

## Resolve what we're talking about

Story-scale position lives in a per-feature work file, `.studious/work/<slug>.json`; epic
position lives in the epic ledger. Both are read and written only through `gate-ledger`.

```bash
gate-ledger work-list     # stories in flight
gate-ledger epic-list     # epics in flight
```

- **`$ARGUMENTS` is empty — "do the next piece."** If a work file's branch matches the
  current branch, that's it. Otherwise, if exactly one epic is `approved`/`running`/`ready`,
  drive that epic — **`proposed` deliberately does not count here** (#311): a brief awaiting
  its viva stamp has not been approved yet, and driving it on an empty invocation would be
  exactly the default-approval this door refuses everywhere else. Otherwise, if exactly one
  work file is active (phase not `done`/`stopped`),
  use it. If several are active, list them and ask which — don't guess. **Cap that list at the
  5 most recently updated** (`updatedAt`), and say how many more there are rather than
  printing them all: a menu long enough to scroll is not a choice a user can make. If the list
  is long, say so and suggest `gate-ledger gc`, which collects finished work files — a flow
  that ended should not still be asking for attention. If nothing is in flight, say so and
  invite `/next [idea, issue, or milestone]`.
- **`$ARGUMENTS` names work in flight** (a slug, branch, title, or epic) — resume it.
- **`$ARGUMENTS` names a milestone, an epic issue, or a label** — epic scale. If no bet is
  approved for it, **route to `/bet <scope>` first**: scope, stories, and appetite are
  approved there and only there. With an approved bet, follow
  `reference/epic-orchestration.md` — it carries the plan piece, the driver, the finale, the
  park queue, and the reporting shape in full. Consult it; don't restate it here.
- **Anything else starts a new story** — a raw idea or an issue reference. For an issue,
  fetch its title and body with `gh issue view` and use them as the bet's input. Derive a
  short slug from the title, then create the work file at phase `decide`:

```bash
gate-ledger work-set --slug "<slug>" --title "<title>" --source "<issue #N or: idea>" --phase decide
```

## Find the piece — evidence first

The work file's `phase` names the next piece, but verify it against evidence before running
anything, and correct the file when they disagree — evidence wins:

- **Recorded verdicts** — read via the ledger tool, never the raw file: `gate-ledger gate-get`
  prints the current branch's recorded verdicts as JSON (`.gates.<gate>.verdict` /
  `.gates.<gate>.sha`); empty output means nothing recorded yet. Staleness is
  **episode-scoped** (`reference/gate-vocabulary.md`), never a cross-episode sha comparison: a
  verdict belongs to the episode that recorded it, and `/review` decides from its own episode
  record whether the next run re-enters that episode or opens a fresh one — don't re-derive
  that here from sha drift. Verdicts route the flow forward only. A delivery-side verdict, or
  the fix commits its findings produce, never re-arms the work episode: that episode's `PASS`
  stands. Where those fixes get judged is `/review`'s own routing call — a targeted fix
  re-enters the delivery episode's re-review round, and a story-scale fix goes through a fresh
  work episode first, an episode `/build` or `/review` opens, never a phase bounce back to
  piece 3 from here. The only other backward route is the user explicitly asking for one. (The PR-time
  reminder still compares recorded shas to HEAD and may nag after post-verdict commits; it is
  non-blocking by design.)
- **Design doc** — the `designDoc` path in the work file, else discover a candidate the way
  `/review`'s design episode does. When found, record it: `work-set --design-doc "<path>"`.
- **Pre-mortem register** — `docs/studious/premortems/<doc-slug>.md`, where `<doc-slug>` is
  the recorded `designDoc`'s filename without its extension — the register is named after the
  design doc, not the feature slug, so don't reuse this flow's `<slug>` here. A register at
  that path with a `Branch:` header matching the current branch is evidence the design episode
  already returned **PROCEED TO PLAN**.
- **Build progress** — implementation commits since the design-review sha. If the phase says
  `build` and there are none, the build piece isn't done: say so rather than advancing
  (re-offering the handoff is fine).
- **Executor-reported build status** — an executor satisfying `reference/worker-contract.md`
  may log its own terminal status for the build piece without setting `--phase` itself (phase
  judgment stays this door's call). Read it with `gate-ledger work-get --slug "<slug>"`'s
  `.history`, most recent `step: "build"` entry. Trust it only when its `sha` is still HEAD —
  commits since mean the report is stale and the commit-evidence check above wins instead. If
  current: `BUILT` corroborates the commit check; `PAUSED` — stay at phase `build`, and say so
  using the reported status rather than a generic "no commits yet"; `ESCALATED` — regress phase
  to `design` and surface the reported reason, the same shape as the design episode's
  `RETHINK`. `HANDED-OFF` and `SKIPPED` are this door's own markers rather than an executor's
  report — they make no claim about the build, so the commit-evidence check governs on its own.
  **Any other token: name it and fall through to commit evidence, never silently.** Say "the
  work file reports build outcome `<token>`, which isn't one this flow recognizes — going by
  commits instead". `bin/gate-ledger` rejects unknown build outcomes on write, so seeing one
  means a record predating that check or a hand-edited file — either way the diff is the ground
  truth, not the label.

## Run exactly one piece

Verdict tokens named below are canonical in `reference/gate-vocabulary.md` — if a door's actual
output ever looks inconsistent with the mapping here, that file (and the door itself) wins.

### 1 · bet

Run `/bet` with the work as its argument, then set the next phase by verdict:

- **BUILD** → phase `design`
- **BUILD SMALLER** → phase `design`, and update the work file title to the scoped-down version
  so every later piece inherits the smaller scope
- **DEFER** / **DON'T BUILD** → phase `stopped`; surface the reasoning and end the flow (the
  user can explicitly restart it later)

```bash
gate-ledger work-log --slug "<slug>" --step decide --outcome "<verdict>" --phase "<next phase>"
```

### 2 · design

This door doesn't author the design doc — the contract is normative
(`reference/design-doc-contract.md`), the route to satisfying it is the user's pick.
Deliberately, so this stays true even though `/shape` ships in this same plugin: an episode
must reach the same verdict regardless of who produced the branch
(`reference/worker-contract.md`), and `scripts/check_gate_independence.py` enforces it in CI.

- **Route is `/shape`:** run it, handing over the bet's verdict, the (possibly scoped-down)
  title, the contract's required sections (point at `templates/design-doc.md` as the
  scaffold), and the source issue if any. `/shape` inventories, interviews, drafts, gets
  viva sign-off section by section, then convenes `/review`'s design episode itself and
  reports its own verdict (`DESIGNED` / `NEEDS RESEARCH` / `REVISED`) plus the convened
  episode's own (`PROCEED TO PLAN` / `REVISE` / `RETHINK`) in one message — read both.
- **Any other route:** a hand-written spec, or Superpowers' brainstorming/planning
  workflow, produces a doc satisfying the contract too — do not draft it yourself, that
  work belongs to the user and their workflow. No producer exists on this route to convene
  the episode, so once such a doc exists on the branch with no `design-review` verdict
  recorded yet, this door runs `/review` against it directly — with a design doc and no
  built diff, bare `/review` opens the design episode — exactly as it always has.

Then, from whichever ran:

- **No doc yet, or `/shape` reports `NEEDS RESEARCH`** → phase stays `design`; a fork needs
  a human answer before anything is drafted.
- **PROCEED TO PLAN** → phase `build`.
- **REVISE** — surviving `/shape`'s own one internal redraft-and-reconvene, or a bare
  `/review`'s first `REVISE` — → phase stays `design-review`; the next piece is
  addressing the listed changes (via whichever route produced the doc), after which it
  re-runs, amending the pre-mortem register in place rather than regenerating it (the
  design episode records via `record`, outside the ledger's round-cap verbs — `/review`'s
  own exception section explains why; `/shape` cites the same exception for its own
  internal round).
- **RETHINK** → phase `design`; back to the doc with the reasoning.

Log with `work-log --step design-review --outcome "<verdict>" --phase "<phase>"` — the
verdict logged is the episode's own token (`PROCEED TO PLAN` / `REVISE` / `RETHINK`,
`reference/gate-vocabulary.md`'s spelling for this gate); `/shape`'s own
`DESIGNED`/`NEEDS RESEARCH`/`REVISED` rides in the report prose, not this field. **Never
`--step design`** — `scripts/retro-stats` buckets rounds and time-per-phase by the gate's
own step name (`GATES`/`PHASES`, both naming `design-review` distinctly from `design`);
logging under the piece's display name instead of the gate name would silently zero out
that gate's row going forward.

**The review model at this scale (#210):** a design doc here gets a human sign-off — viva
inside `/shape`, or whatever your route's equivalent is — *and* the design episode, because a
human signs off where an episode cannot verify mechanically. That is the same rule that keeps
prompt-prose and idea-shaped stories supervised rather than dispatched
(`reference/epic-plan-contract.md`, "Story class").

### 3 · build

- **Route is `/build`:** run it, handing over the design doc path, the pre-mortem register
  path (its items are what the work and delivery episodes verify at the end), the scoped
  title, and the source issue if any. Once a feature branch exists, record it — the gate
  ledger is per-branch, so later pieces need it: `work-set --branch "<branch>"`. `/build`
  plans, builds one task at a time, exorcises, then convenes `/review`'s work episode
  itself — dispatching a fix and re-convening once on its own `FIX AND RE-REVIEW`, exactly
  once, before handing an unresolved fix cycle back — and reports its own verdict
  (`BUILT` / `PAUSED` / `ESCALATED`) plus the convened episode's own (`PASS` /
  `FIX AND RE-REVIEW` / `NEEDS DISCUSSION`) in one message — read both.
- **Any other route:** Superpowers' plan/execute workflow, or hand-implemented code,
  builds however the user likes — no episode cares which, deliberately, for the same
  reason piece 2 states. No producer exists on this route to convene the episode, so once
  implementation commits exist on the branch, this door runs `/review` against the built
  diff directly — bare `/review` opens the work episode with a built diff present — exactly
  as it always has. Each run is one round of that bounded episode; `/review` owns the
  episode bookkeeping (`bin/gate-ledger`'s episode verbs: open, re-enter, verdict, with the
  round cap enforced in code), so never count rounds or decide re-entry here.

Then, from whichever ran:

- **No commits yet** → phase stays `build`.
- **`PAUSED`** → phase stays `build`; surface `/build`'s own named cause (a dirty baseline,
  a `REPLAN`, a risk-tagged pause, a script usage error, or its convened episode's own round
  cap / convergence refusal) and resume action.
- **`ESCALATED`** → phase regresses to `design`; surface the reported reason.
- **`PASS`** (`/build`'s convened episode, or `/review` run directly) → phase `acceptance`;
  the work episode is closed.
- **`NEEDS DISCUSSION`** → phase stays `build`; surface the concerns — the user decides how
  to resolve them.
- **`FIX AND RE-REVIEW`** surviving `/build`'s own one internal fix-and-reconvene, or a bare
  `/review`'s first `FIX AND RE-REVIEW` → phase stays `build`; the next piece is fixing the
  blocking findings (via whichever route produced the branch) then re-running — that run
  **re-enters the same episode** for its one re-review round, narrowed to the blocking
  lanes, never a fresh review from scratch. If it reports the round cap or a convergence
  refusal instead, surface the choice named — record a terminal verdict, reopen a fresh
  episode, or take the still-open findings to discussion — and let the user make it.

Log with `work-log --step audit --outcome "<verdict>" --phase "<phase>"` — the verdict
logged is the episode's own token (`reference/gate-vocabulary.md`'s spelling for the
`audit` gate); `/build`'s own `BUILT`/`PAUSED`/`ESCALATED` rides in the report prose, not
this field. **Never `--step build`** — `bin/gate-ledger` closes that step's outcome
vocabulary to `BUILT`/`PAUSED`/`ESCALATED`/`HANDED-OFF`/`SKIPPED` (#213) and refuses a
gate token like `PASS` written under it.

Whatever the verdict, run `gate-ledger episode-get --gate audit` and carry its first line —
`round R of C — N open, M carried` — into the closing block, verbatim: the episode's own round
and finding counts, never a re-tally of the report. If it prints nothing (no episode recorded
on this branch — a legacy ledger, a driver-recorded verdict, or no `jq`), carry `none recorded`
instead — never invent counts.

### 4 · delivery review

Run `/review --delivery`. This is the branch's bounded delivery episode, and it runs at the
delivery boundary — after the work episode closed `PASS`, before the PR — never as a per-fix
loop. Then:

- **SHIP** → phase `finish`; the delivery episode is closed
- **FIX AND RE-REVIEW** → phase stays `acceptance`; the next piece is landing the listed fixes,
  then running `/review --delivery` again for the episode's one re-review round. `/review`
  itself routes a story-scale fix through the work episode; a delivery verdict
  never re-arms the work episode from here.
- **HOLD** → phase stays `acceptance`; surface the product concerns — rework beyond targeted
  fixes is the user's call

Log with `work-log --step acceptance --outcome "<verdict>" --phase "<phase>"`.

Whatever the verdict, run `gate-ledger episode-get --gate acceptance` and carry its first line
into the closing block, verbatim — same rule as piece 3, same `none recorded` fallback.

### 5 · ship — handoff

Both episodes have passed. Closing out is a handoff, not a judgment — there is no verdict to
record here.

Hand over and stop:

- The verdict trail (every episode, its token, and the sha it was recorded at), and the
  pre-mortem register path.
- Name `/ship` as the route that ships with this plugin: it assembles the evidence table,
  removes the branch-local scaffolding, and ends in one of `MERGE` / `PR` / `KEEP` / `DISCARD`.
  Doing it by hand is equally fine — no episode cares which, and nothing downstream reads a
  `/ship` artifact.
- The PR is the user's to open either way.

Log `work-log --step finish --outcome HANDED-OFF --phase done`.

## Skips

Doors are optional by judgment — but that judgment is the user's. Skip a piece only when the
user explicitly says to; log it (`work-log --step <piece> --outcome SKIPPED --phase <next>`)
and move on. Never skip on your own initiative, and never treat a fix-and-retry verdict as
skippable.

## Close every invocation the same way

After the piece finishes, end with exactly this shape and nothing after it:

```text
Flow: <slug> — piece <k>/5 (<name>): <outcome>.
Next piece: <name> — <one clause on what it involves>.
Say "next" when you're ready, or run /next.
```

When the piece just run was build (3) or the delivery review (4), insert that
episode's readout as a second line — the `round R of C — N open, M carried` line the piece read
from `gate-ledger episode-get --gate <audit|acceptance>`, verbatim:

```text
Episode: round R of C — N open, M carried
```

When the flow reaches `done` or `stopped`, the last two lines become the wrap-up instead:
`done` points at `gh pr create`; `stopped` states the verdict that ended it.

At epic scale the closing shape is `reference/epic-orchestration.md`'s own report — the run
summary, the "Needs you" queue, and the held/landed counts — not this block.

Then stop. Do not start the next piece, do part of it "to save time," or ask whether to
continue — the user advances the flow with one word, when ready.

## Record keeping

All flow state goes through `gate-ledger` — `work-set`, `work-log`, `work-get`, `work-list` for
story state, `epic-list`/`epic-get` for epic state, and `gate-get` to read recorded verdicts —
never hand-edit the JSON or read either store's files directly. The files are local and
gitignored; they never enter the repo. If `gate-ledger` is not found (the plugin's `bin/` isn't
on `PATH` in this environment), tell the user flow position can't be recorded — do not skip
silently — and navigate from evidence alone for this session.
