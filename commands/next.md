---
description: The standup question at any scale — where is this, and what now. Reads position from recorded state and repo evidence, names the next door, and runs it on your word. One story, a list, or a whole milestone. Use for "what's next", "do the next piece", "where am I", "keep going", "drive this milestone".
argument-hint: "[idea, issue, milestone, or in-flight work] (omit to continue what's in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Workflow
---

# What's next

One door for "where am I, what now" — at story scale, list scale, or milestone scale. The
flow is scale-invariant: the same doors in the same order, whatever the size. Scope changes
how many stories a bet contains and how much runs dispatched versus supervised; it never
changes which doors exist.

This door judges nothing and builds nothing. It reads position, names the next door, and
runs it on your word. Verdicts belong to `/review`; commits belong to `/build` and `/ship`.

Read PRODUCT.md at the project root first.

## Report first, run on confirmation

**Default: report, then ask.** Say where the work stands, name the next door and what it
involves, and stop for the user's word before running it. Propose, don't apply.

**One exception, because re-asking an answered question is friction, not safety:** if the
previous turn's closing block already named this exact piece and the user's message is an
advance ("next", "go", "keep going", a bare `/next`), that *is* the confirmation — run it
without asking again.

**Never auto-advance past the piece you ran.** When it finishes — pass, fail, or handoff —
stop with the closing block below, even when the result is a clean pass and the next step is
obvious. The user advances the flow; you never do.

**When recorded state and the repo disagree, stop and name the disagreement.** Do not guess
which is right and do not quietly pick one. Evidence usually wins (see below), but a
contradiction the evidence rules can't settle is a question for the user, not a coin flip.

## The flow

| # | Piece | Door | Done when |
|---|-------|------|-----------|
| 1 | bet | `/bet` | verdict recorded (**BUILD** / **BUILD SMALLER** continue) |
| 2 | shape | handoff | a design doc exists satisfying `reference/design-doc-contract.md` |
| 3 | design review | `/review` | **PROCEED TO PLAN** |
| 4 | build | handoff | implementation commits exist on the feature branch |
| 5 | work review | `/review` | **PASS** closes the work episode |
| 6 | delivery review | `/review --delivery` | **SHIP** closes the delivery episode |
| 7 | ship | handoff | branch closed out: scaffolding removed, evidence assembled, PR opened or work merged/parked |

Pieces 2, 4, and 7 are handoffs — the two steps Studious doesn't own (writing the design,
writing the code) plus closeout. Studious hands over context and steps back; the route is
the user's pick, and no episode cares which route produced the branch.

After piece 7 the flow is `done`. Never open the PR yourself: the PR is the user's
(`gh pr create` — the PR-time hook reads the same ledger).

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
  drive that epic. Otherwise, if exactly one work file is active (phase not `done`/`stopped`),
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
  work episode first, an episode `/review` opens, never a phase bounce back to piece 5 from
  here. The only other backward route is the user explicitly asking for one. (The PR-time
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

### 2 · shape — handoff

This door doesn't author the design doc — the contract is normative
(`reference/design-doc-contract.md`), the route to satisfying it is the user's pick.
Deliberately, so this stays true even though `/shape` ships in this same plugin: an episode
must reach the same verdict regardless of who produced the branch
(`reference/worker-contract.md`), and `scripts/check_gate_independence.py` enforces it in CI.
Set them up, then stop:

- Hand over the bet's verdict, the (possibly scoped-down) title, and the contract's required
  sections; point at `templates/design-doc.md` as the scaffold.
- Name `/shape` as the route that ships with this plugin — batch interview → drafted doc →
  viva sign-off — which produces a doc satisfying the contract.
- If Superpowers is installed, its brainstorming and planning workflow produces a satisfying
  doc too. So does any hand-written spec.
- Do not draft the doc yourself. It may well get written right here in the session — that work
  belongs to the user and their workflow, not to this door.

Log the handoff: `work-log --step design --outcome HANDED-OFF` (phase stays `design`; the
evidence check advances the flow once the doc exists).

### 3 · design review

Run `/review` against the recorded doc — with a design doc and no built diff, bare `/review`
opens the design episode. Then:

- **PROCEED TO PLAN** → phase `build`
- **REVISE** → phase stays `design-review`; the next piece is addressing the listed changes,
  after which `/review` re-enters the same episode for its one revision round
- **RETHINK** → phase `design`; back to the doc with the reasoning

Log with `work-log --step design-review --outcome "<verdict>" --phase "<phase>"`.

**The review model at this scale (#210):** a design doc here gets a human sign-off — viva
inside `/shape`, or whatever your route's equivalent is — *and* the design episode, because a
human signs off where an episode cannot verify mechanically. That is the same rule that keeps
prompt-prose and idea-shaped stories supervised rather than dispatched
(`reference/epic-plan-contract.md`, "Story class").

### 4 · build — handoff

The flow hands off rather than builds. Hand over the working context, then stop:

- The design doc path, the pre-mortem register path (its items are what the work and delivery
  episodes verify at the end), the scoped title, and the source issue if any.
- Once a feature branch exists, record it — the gate ledger is per-branch, so later pieces need
  it: `work-set --branch "<branch>"`.
- Name `/build` as the route that ships with this plugin: it plans, then builds, and reports
  `BUILT | PAUSED | ESCALATED` back into this work file, so the next `/next` invocation resumes
  from that without asking.
- If Superpowers is installed, its plan/execute workflow picks up from the design doc instead.
  Either way the user builds however they like — no episode cares which. Deliberately, for the
  same reason piece 2 states.

Log `work-log --step build --outcome HANDED-OFF`. Phase stays `build`; the evidence check
advances it when implementation commits exist.

### 5 · work review

Run `/review` — with a built diff, bare `/review` opens the work episode. Each run is one round
of that bounded episode; `/review` owns the episode bookkeeping (`bin/gate-ledger`'s episode
verbs: open, re-enter, verdict, with the round cap enforced in code), so never count rounds or
decide re-entry here. Then:

- **PASS** → phase `acceptance`; the work episode is closed
- **FIX AND RE-REVIEW** → phase stays `audit`; the next piece is fixing the blocking findings,
  then running `/review` again — that run **re-enters the same episode** for its one re-review
  round, narrowed to the blocking lanes, never a fresh review from scratch. If `/review`
  reports the round cap instead, surface its choice — reopen a fresh episode or take the
  still-open findings to discussion — and let the user make it.
- **NEEDS DISCUSSION** → phase stays `audit`; surface the concerns — the user decides how to
  resolve them

Log with `work-log --step audit --outcome "<verdict>" --phase "<phase>"`.

Whatever the verdict, run `gate-ledger episode-get --gate audit` and carry its first line —
`round R of C — N open, M carried` — into the closing block, verbatim: the episode's own round
and finding counts, never a re-tally of the report. If it prints nothing (no episode recorded
on this branch — a legacy ledger, a driver-recorded verdict, or no `jq`), carry `none recorded`
instead — never invent counts.

### 6 · delivery review

Run `/review --delivery`. This is the branch's bounded delivery episode, and it runs at the
delivery boundary — after the work episode closed `PASS`, before the PR — never as a per-fix
loop. Then:

- **SHIP** → phase `finish`; the delivery episode is closed
- **FIX AND RE-REVIEW** → phase stays `acceptance`; the next piece is landing the listed fixes,
  then running `/review --delivery` again for the episode's one re-review round. `/review`
  itself routes a story-scale fix through the work episode; a delivery verdict never re-arms
  the work episode from here.
- **HOLD** → phase stays `acceptance`; surface the product concerns — rework beyond targeted
  fixes is the user's call

Log with `work-log --step acceptance --outcome "<verdict>" --phase "<phase>"`.

Whatever the verdict, run `gate-ledger episode-get --gate acceptance` and carry its first line
into the closing block, verbatim — same rule as piece 5, same `none recorded` fallback.

### 7 · ship — handoff

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
Flow: <slug> — piece <k>/7 (<name>): <outcome>.
Next piece: <name> — <one clause on what it involves>.
Say "next" when you're ready, or run /next.
```

When the piece just run was the work review (5) or the delivery review (6), insert that
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
continue — the whole point is that the user advances the flow with one word, whenever they're
ready.

## Record keeping

All flow state goes through `gate-ledger` — `work-set`, `work-log`, `work-get`, `work-list` for
story state, `epic-list`/`epic-get` for epic state, and `gate-get` to read recorded verdicts —
never hand-edit the JSON or read either store's files directly. The files are local and
gitignored; they never enter the repo. If `gate-ledger` is not found (the plugin's `bin/` isn't
on `PATH` in this environment), tell the user flow position can't be recorded — do not skip
silently — and navigate from evidence alone for this session.
