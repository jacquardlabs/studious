---
description: Navigate the feature flow one piece at a time — run the next step without needing to know the full workflow
argument-hint: "[idea, issue number, or in-flight feature] (omit to do the next piece)"
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Work on a feature

Walk one feature through the per-feature gate flow, one piece per invocation. This command owns *which step comes next* — the what and the whether — never the how. It runs Studious's own gates directly and, at the two steps Studious doesn't own (writing the design doc, building), hands over context and steps back.

**One invocation, one piece. Never auto-advance.** When the piece finishes — pass, fail, or handoff — stop and hand control back with the closing block below, even when the result is a clean pass and the next step is obvious. The user advances the flow; you never do.

Read PRODUCT.md at the project root first.

## The flow being navigated

| # | Piece | Owner | The piece is done when |
|---|-------|-------|------------------------|
| 1 | decide | `/gate-should-we-build` | verdict recorded (**BUILD** / **BUILD SMALLER** continue the flow) |
| 2 | design | handoff — Studious steps back | a design doc exists satisfying `reference/design-doc-contract.md` |
| 3 | design-review | `/gate-design-review` | **PROCEED TO PLAN** |
| 4 | build | handoff — Studious steps back | implementation commits exist on the feature branch |
| 5 | audit | `/gate-audit` | **PASS** closes the work episode |
| 6 | acceptance | `/gate-acceptance` | **SHIP** closes the delivery episode |
| 7 | finish | handoff — Studious steps back | the branch is closed out: scaffolding removed, evidence assembled, PR opened or the work merged/parked |

Piece 4 covers planning as well as building — the route it hands to (`/plan` then `/build`) is two skills but one handoff, so there is no separate plan piece to stop at.

After piece 7 the flow is `done`. Never open the PR yourself: piece 7 hands over, and whether the user runs `/finish` or does it by hand, the PR is theirs (`gh pr create` — the PR-time hook reads the same ledger).

**This flow and `/coach`'s are the same flow.** `/coach` names the build skills at a finer grain (`/design`, `/plan`, `/build`, `/finish` as separate dispatches) because dispatching them one at a time is its job; this command groups them into handoff pieces because running the gates is its job. They read and write the same work file, so a feature tracked here is visible there and vice versa. The difference is posture, not position: **`/work-on` runs the gate and records the verdict; `/coach` only reads and recommends, and dispatches a build skill on explicit confirmation.** Use `/work-on` to advance a feature; use `/coach` when you're re-entering cold and want to be told where you are.

For the gate pieces, run that slash command's workflow now, with the flow's context as its input — each gate owns its own logic and records its own verdict; don't restate or reimplement it here.

## Resolve the feature

Flow position lives in a per-feature work file, `.studious/work/<slug>.json`, read and written only through the ledger tool (see Record keeping). See what's in flight with:

```bash
gate-ledger work-list
```

- **`$ARGUMENTS` is empty — "do the next piece."** If a work file's branch matches the current branch, that's the feature. Otherwise, if exactly one work file is active (phase not `done`/`stopped`), use it. If several are active, list them and ask which — don't guess. **Cap that list at the 5 most recently updated** (`updatedAt`), and say how many more there are rather than printing them all: a menu long enough to scroll is not a choice a user can make. If the list is long, say so plainly and suggest `gate-ledger gc`, which collects finished work files — a flow that ended should not still be asking for attention. If none exist, say there's no feature in flight and invite `/work-on [idea or issue]`.
- **`$ARGUMENTS` names in-flight work** (matches a slug, branch, or title) — resume that feature.
- **Anything else starts a new feature** — a raw idea or an issue reference. For an issue, fetch its title and body with `gh issue view` and use them as the gate input. Derive a short slug from the title, then create the work file at phase `decide`:

```bash
gate-ledger work-set --slug "<slug>" --title "<title>" --source "<issue #N or: idea>" --phase decide
```

## Find the next piece — evidence first

The work file's `phase` names the next piece, but verify it against evidence before running anything, and correct the file when they disagree — evidence wins:

- **Gate verdicts** — read via the ledger tool, never the raw file: `gate-ledger gate-get` prints the current branch's recorded verdicts as JSON (`.gates.<gate>.verdict` / `.gates.<gate>.sha`); empty output means nothing recorded yet. Staleness is **episode-scoped** (`reference/gate-vocabulary.md`), never a cross-gate sha comparison: a verdict belongs to the episode that recorded it, and each gate's own door decides from its episode record whether the next run re-enters that episode or opens a fresh one — don't re-derive that here from sha drift. Verdicts route the flow forward only. An acceptance-side verdict, or the fix commits its findings produce, never re-arms `audit`: the work episode's `PASS` stands as that episode's verdict. Where those fixes get judged is the delivery door's own routing call (`commands/gate-acceptance.md` owns it): a targeted fix re-enters the delivery episode's re-review round, and a story-scale fix goes through a fresh work episode first — a fresh episode the door opens, never a re-arming of the closed one, and never a phase bounce back to piece 5 from here. The only other backward route is the user explicitly asking for one. (The PR-time reminder still compares recorded shas to HEAD and may nag after post-verdict commits; it is non-blocking by design.)
- **Design doc** — the `designDoc` path in the work file, else discover a candidate the way `/gate-design-review` does. When found, record it: `work-set --design-doc "<path>"`.
- **Pre-mortem register** — `docs/studious/premortems/<doc-slug>.md`, where `<doc-slug>` is the recorded `designDoc`'s filename without its extension — `/gate-design-review` names the register after the design doc, not the feature slug, so don't reuse this flow's `<slug>` here. A register found at that path with a `Branch:` header matching the current branch is evidence design-review already returned **PROCEED TO PLAN**.
- **Build progress** — implementation commits since the design-review sha. If the phase says `build` and there are none, the build piece isn't done: say so rather than advancing (re-offering the handoff is fine).
- **Executor-reported build status** — an executor satisfying `reference/worker-contract.md` may log its own terminal status for the build piece without setting `--phase` itself (phase judgment stays this command's call). Read it with `gate-ledger work-get --slug "<slug>"`'s `.history`, most recent `step: "build"` entry. Trust it only when its `sha` is still HEAD — commits since mean the report is stale and the commit-evidence check above wins instead. If current: `BUILT` corroborates the commit check; `PAUSED` — stay at phase `build`, and say so using the reported status rather than a generic "no commits yet"; `ESCALATED` — regress phase to `design` and surface the reported reason, the same shape as design-review's `RETHINK` → `design` below. `HANDED-OFF` and `SKIPPED` are this command's own markers rather than an executor's report — they make no claim about the build, so the commit-evidence check above governs on its own. **Any other token: name it and fall through to commit evidence, never silently.** Say "the work file reports build outcome `<token>`, which isn't one this flow recognizes — going by commits instead". `bin/gate-ledger` rejects unknown build outcomes on write, so seeing one means a record predating that check (`DONE`, from an older `/work-through` driver) or a hand-edited file — either way the diff is the ground truth, not the label.

## Run exactly one piece

Verdict tokens named below are canonical in `reference/gate-vocabulary.md` — if a gate's
actual output ever looks inconsistent with the mapping here, that file (and the gate command
itself) wins.

### 1 · decide

Run `/gate-should-we-build` with the feature as its argument, then set the next phase by verdict:

- **BUILD** → phase `design`
- **BUILD SMALLER** → phase `design`, and update the work file title to the scoped-down version so every later piece inherits the smaller scope
- **DEFER** / **DON'T BUILD** → phase `stopped`; surface the gate's reasoning and end the flow (the user can explicitly restart it later)

```bash
gate-ledger work-log --slug "<slug>" --step decide --outcome "<verdict>" --phase "<next phase>"
```

### 2 · design — handoff

This command doesn't author the design doc — the contract is normative (`reference/design-doc-contract.md`), the route to satisfying it is the user's pick — deliberately, so this stays true even now that `/design` ships in this same plugin: a gate must reach the same verdict regardless of who produced the branch (`reference/worker-contract.md`), and `scripts/check_gate_independence.py` enforces it in CI. Set them up, then stop:

- Hand over the decide verdict, the (possibly scoped-down) title, and the contract's required sections; point at `templates/design-doc.md` as the scaffold.
- Name `/studious:design` as the route that ships with this plugin — batch interview → drafted doc → viva sign-off — and produces a doc satisfying the contract. Qualified, not bare: a bare `/design` collides with a Claude Code built-in of the same name.
- If Superpowers is installed, its brainstorming and planning workflow produces a satisfying doc too. So does any hand-written spec.
- Do not draft the doc yourself. It may well get written right here in the session — that work belongs to the user and their workflow, not to this command.

Log the handoff: `work-log --step design --outcome HANDED-OFF` (phase stays `design`; the evidence check advances the flow once the doc exists).

### 3 · design-review

Run `/gate-design-review` against the recorded doc, then:

- **PROCEED TO PLAN** → phase `build`
- **REVISE** → phase stays `design-review`; the next piece is addressing the listed changes, after which this gate re-runs
- **RETHINK** → phase `design`; back to the doc with the gate's reasoning

Log with `work-log --step design-review --outcome "<verdict>" --phase "<phase>"`.

**The review model on this pipeline (#210):** a design doc here gets a human sign-off —
viva inside `/design`, or whatever your route's equivalent is — *and* this gate, because
a human signs off where a gate cannot verify mechanically, which is the same rule that
sends prompt-prose and idea-shaped stories here from `/work-through`'s plan piece
(`reference/epic-plan-contract.md`, "Story class") rather than into an unattended epic.

### 4 · build — handoff

The flow hands off rather than builds. Hand over the working context, then stop:

- The design doc path, the pre-mortem register path (its items are what `/gate-audit` and `/gate-acceptance` verify at the end), the scoped title, and the source issue if any.
- Once a feature branch exists, record it — the gate ledger is per-branch, so later pieces need it: `work-set --branch "<branch>"`.
- Name `/studious:plan` + `/studious:build` as the route that ships with this plugin (`/plan`, bare, has no Claude Code built-in to collide with today, but qualify it too for consistency with `/design`): it picks up from the design doc and reports `BUILT | PAUSED | ESCALATED` back into this work file (see "Find the next piece — evidence first" below), so the next `/work-on` invocation resumes from that without asking.
- If Superpowers is installed, its plan/execute workflow picks up from the design doc instead. Either way the user builds however they like — no gate cares which. Deliberately, so this stays true even now that `/plan` and `/build` ship in this same plugin: a gate must reach the same verdict regardless of who produced the branch (`reference/worker-contract.md`), and `scripts/check_gate_independence.py` enforces it in CI.

Log `work-log --step build --outcome HANDED-OFF`. Phase stays `build`; the evidence check advances it when implementation commits exist.

### 5 · audit — the work episode

Run `/gate-audit`. Each run is one round of the branch's bounded **work episode**; the door owns the episode bookkeeping (`bin/gate-ledger`'s episode verbs: open, re-enter, verdict, with the round cap enforced in code), so never count rounds or decide re-entry here. Then:

- **PASS** → phase `acceptance`; the work episode is closed
- **FIX AND RE-REVIEW** → phase stays `audit`; the next piece is fixing the blocking findings, then running `/gate-audit` again — that run **re-enters the same episode** for its one re-review round, narrowed to the blocking lanes, never a fresh audit from scratch. If the door reports the round cap instead, surface its choice — reopen a fresh episode or take the still-open findings to discussion — and let the user make it.
- **NEEDS DISCUSSION** → phase stays `audit`; surface the concerns — the user decides how to resolve them

Log with `work-log --step audit --outcome "<verdict>" --phase "<phase>"`.

Whatever the verdict, run `gate-ledger episode-get --gate audit` and carry its first line — `round R of C — N open, M carried` — into the closing block below, verbatim: the episode's own round and finding counts, never a re-tally of the report. If it prints nothing (no episode recorded on this branch — a legacy ledger, a driver-recorded verdict, or no `jq`), carry `none recorded` instead — never invent counts.

### 6 · acceptance — the delivery episode

`/gate-acceptance` is the branch's bounded **delivery episode**, and it runs at the delivery boundary — after the work episode closed `PASS`, before the PR — never as a per-fix loop. Run it, then:

- **SHIP** → phase `finish`; the delivery episode is closed
- **FIX AND RE-REVIEW** → phase stays `acceptance`; the next piece is landing the listed fixes, then running `/gate-acceptance` again for the episode's one re-review round. The door itself routes a story-scale fix through the work episode (`commands/gate-acceptance.md` owns that routing); an acceptance verdict never re-arms the work episode from here.
- **HOLD** → phase stays `acceptance`; surface the product concerns — rework beyond targeted fixes is the user's call

Log with `work-log --step acceptance --outcome "<verdict>" --phase "<phase>"`.

Whatever the verdict, run `gate-ledger episode-get --gate acceptance` and carry its first line into the closing block below, verbatim — same rule as piece 5, same `none recorded` fallback when it prints nothing.

### 7 · finish

Both gates have passed. Closing out is a handoff, not a gate — there is no verdict to record here.

Hand over and stop:

- The verdict trail (every gate, its token, and the sha it was recorded at), and the pre-mortem register path.
- Name `/studious:finish` as the route that ships with this plugin: it assembles the evidence table, removes the branch-local scaffolding (`docs/design/<slug>.md`, `PLAN.md`), and ends in one of `MERGE` / `PR` / `KEEP` / `DISCARD`. Doing it by hand is equally fine — no gate cares which, and nothing downstream reads a `/finish` artifact.
- The PR is the user's to open either way.

Log `work-log --step finish --outcome HANDED-OFF --phase done`.

## Skips

Gates are optional by judgment — but that judgment is the user's. Skip a piece only when the user explicitly says to; log it (`work-log --step <piece> --outcome SKIPPED --phase <next>`) and move on. Never skip on your own initiative, and never treat a fix-and-retry verdict as skippable.

## Close every invocation the same way

After the piece finishes, end with exactly this shape and nothing after it:

```text
Flow: <slug> — piece <k>/7 (<name>): <outcome>.
Next piece: <name> — <one clause on what it involves>.
Run /work-on when you're ready, or just say "next".
```

When the piece just run was audit (piece 5) or acceptance (piece 6), insert that episode's readout as a second line — the `round R of C — N open, M carried` line the piece read from `gate-ledger episode-get --gate <audit|acceptance>`, verbatim:

```text
Episode: round R of C — N open, M carried
```

When the flow reaches `done` or `stopped`, the last two lines become the wrap-up instead: `done` points at `gh pr create`; `stopped` states the verdict that ended it.

Then stop. Do not start the next piece, do part of it "to save time," or ask whether to continue — the whole point is that the user advances the flow with one word, whenever they're ready.

## Record keeping

All flow state goes through `gate-ledger` — `work-set`, `work-log`, `work-get`, `work-list` for this flow's own state, and `gate-get` to read gate verdicts — never hand-edit the JSON or read either store's files directly. The files are local and gitignored; they never enter the repo. If `gate-ledger` is not found (the plugin's `bin/` isn't on `PATH` in this environment), tell the user flow position can't be recorded — do not skip silently — and navigate from evidence alone for this session.
