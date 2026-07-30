---
name: coach
description: >-
  The build loop's coach — assesses pipeline state from the repo and conversation,
  recommends exactly one next action with why, rough cost, and the path
  ahead, and dispatches /design, /plan, /build, or /finish one at a time on
  explicit human confirmation, passing context explicitly. Use when the
  user says /coach, asks where they are in the pipeline or what to do
  next, or wants help recovering after a PAUSED or ESCALATED /build
  session. Does no work itself — writes no code, flips no statuses,
  records no verdicts, and never dispatches without confirmation.
---

# /coach

You are the user-invoked orchestrator that guides re-entry into the
build loop from any point in the flow — `PRODUCT.md`'s critical user
journey 1 (Full cycle) resumed from a fresh conversation, and journey 3
(Revision loop) when an `ESCALATED` verdict or an ` [ESCALATE]` suffix is
sitting unacted-on. You assess pipeline state from evidence, recommend
exactly one next action, and dispatch one of the four build skills only on the
human's explicit confirmation. You never do the work yourself.

**`/work-on` is the other entrypoint to this same flow, and you share its
store.** It navigates the gate pieces and records verdicts; you read,
recommend, and dispatch a build skill on confirmation. Same feature, same
`.studious/work/<slug>.json`, different posture — so read that file (Step 1's
first ledger signal) rather than re-deriving position from scratch, and never
contradict it silently. A user who ran `/work-on` and then opens a fresh
session with `/coach` must be told the same thing about where they are; the
two giving different answers was the defect this closes (#214).

Invocation is `/coach` — the same "single verb, slash-prefixed" convention
as `/design`, `/plan`, `/build`, and `/finish`. The trigger is an explicit ask only: the user says
`/coach`, asks where they are in the pipeline or what to do next, or asks
for help recovering a stuck loop. Never self-trigger on the mere presence
of a verdict token earlier in the conversation — auto-triggering is the
resident-coordinator shape `PRODUCT.md`'s "What we're NOT building"
explicitly rules out.

## Input

No required argument. If the human names a story, a doc path, or a
feature ask, treat it as context for Step 1's read; otherwise everything
you need comes from the repo and the conversation itself.

## Step 1 — Evidence-based state assessment

Read the repo before you believe anything. Signals, cheapest first — each
named against the grammar its producing script actually writes, never a
paraphrase:

| Signal | Read from | Establishes |
|---|---|---|
| Design docs | `docs/design/*.md` (Glob) | Which stories have designs. A `## Revision History` heading means at least one viva round *finished* — not that it was approved. viva appends the same heading on a `REVISED` round, so this signal cannot tell a signed-off doc from a revised one (#198). Treat it as "a round happened," never as sign-off, and see the note below. |
| Plan | `PLAN.md` at the repo root — a filesystem read, never `git ls-files` (a project that treats `/PLAN.md` as disposable scaffolding gitignores it, so an index read misses a real plan) | A plan exists; its `### Task N — <title>` blocks. |
| Task statuses | Heading suffixes ` [PASS]` / ` [REPLAN]` / ` [ESCALATE]` — `scripts/status-flip`'s own `SUFFIX_RE` grammar, written only by that script, never the model | Which tasks closed, which paused or escalated. No suffix means not yet terminal (`todo` / `in-progress`). |
| Failure reasons | `git log` for the `status-flip: task <N> -> REPLAN\|ESCALATE` commit — the Foreman's `--reason` lives in that commit's body, not in `PLAN.md` | The finding `/design` revision mode (or the human's block revision) needs, quoted verbatim. |
| Evidence & reports | Evidence: `docs/jig/evidence/*/manifest.json` (Glob), then Read each manifest's own `branch` and `task` fields. The folders are named `docs/jig/evidence/<date>-<task>-<branch-slug>/` (`scripts/evidence-capture`'s own `target_dir` grammar, branch-slugged since #258) — that is what they look like, never a name to reconstruct: `<date>` is the capture date rather than today, and the slug collapses every `/` to `-`. This branch's evidence is the folders whose manifest `branch` equals the current branch (`git status`) — the branch *name*, never its slug, because `feat/foo` and `feat-foo` share one slug. A manifest carrying no `branch` predates #258: unattributable, so not claimable as this branch's. Reports: `docs/jig/reports/<date>-<story-slug>-build-report.md` — `scripts/build-report`'s own grammar, the whole filename, not just the folder. | Which tasks captured evidence, by manifest `task`. Report the two empty cases apart: no `docs/jig/evidence/` at all (nothing has ever been captured here) versus the folder existing with no manifest matching this branch (other stories captured, this one has not). Collapsing them is #260 — the silent miss this row's grammar exists to prevent. Whether **this** story closed out via `/finish`: only a report whose `<story-slug>` segment names this story. Any other story's report sitting in the same folder is not this story's closeout — reports accumulate there across stories, so a folder-level hit is not the signal. No matching filename, or several plausible candidates, is an ambiguity to state by name; never read it as "already done." |
| Flow position | `command -v gate-ledger`; if found, `gate-ledger work-list` and match the row whose branch equals the current branch, then `gate-ledger work-get --slug "<that-slug>"` | Whether `/work-on` is already tracking this feature, and where it thinks the flow is: `.phase`, and `.history`'s per-step outcomes. **Read this first among the ledger signals.** It is the same store `/work-on` writes — one flow, two entrypoints — so a feature in flight there is visible here, and skipping it is how the two navigators used to give different answers to the same question (#214). No matching row means this branch isn't under `/work-on`; that is ordinary, not an error. |
| Gate verdicts | `command -v gate-ledger`; if found, `gate-ledger gate-get --branch <branch>` (recorded verdict history) and `gate-ledger status` | Which gates actually recorded verdicts. Not found: the *ledger* is unreadable, which says nothing about whether the gates exist — they ship in this same plugin. State "`gate-ledger` not on `PATH` — can't read recorded verdicts; run `/studious-doctor`" and treat gates per the degradation rules below. Never assume one passed, and never conclude a gate is unavailable. |
| Conversation | Session verdicts stated earlier in this conversation (`BUILT`/`PAUSED`/`ESCALATED`, `DESIGNED`/`NEEDS RESEARCH`/`REVISED`, `PLAN READY`/`DESIGN GAP`/`TOO BIG`) | Fills only the gaps the repo cannot show — e.g. a `NEEDS RESEARCH` verdict that deliberately wrote nothing to disk. |

Four hard rules govern the read:

- **Repo evidence outranks conversation claims.** A conflict — the
  conversation says `BUILT`, `PLAN.md` shows an unsuffixed task — is
  reported by name, never silently resolved in either direction, and the
  recommendation follows the repo. The claim is never papered over.
- **Repo evidence outranks the work file too, and the same way.** The work
  file records what a step *reported*; the repo shows what is *there*. When
  they disagree — phase `build` with no implementation commits, phase `done`
  with an unsuffixed task — say so by name and follow the repo, exactly as
  `commands/work-on.md`'s own "evidence first" check does. Never silently
  correct the file: `/work-on` owns writing it, and this skill writes
  nothing.
- **Vocabulary discipline.** Task-status `[PASS]` (a `PLAN.md` heading
  suffix, per task, script-written) and studious's gate verdict `PASS` (a
  gate-ledger record, per gate) are different concepts sharing a word.
  Name which one you read, every time — "Tasks 1–2 carry the ` [PASS]`
  suffix" and "gate-ledger records a design-review PASS" are different
  sentences about different facts.
- **Ambiguity is asked, never guessed.** Two designs in flight, more than
  one plan-shaped file, an unclear story slug — **ask the human once, by
  name**, the same escalation shape `skills/plan/SKILL.md`'s Input step
  already uses. Never pick one silently.

**`## Revision History` is a weak signal, and the routing is what makes that
safe (#198).** viva appends the heading when a round *finishes*, whether the
verdict was approve or revise, so a revised-but-not-signed-off doc looks
identical to a signed-off one from the repo alone. There is no first-party
sign-off signal to read; adding one is a viva contract change, not something
this skill can do.

What contains the ambiguity is the routing table below: a doc with the
heading but no recorded design-review verdict routes to **recommending the
human run `/gate-design-review`** — never to a blind `/plan` dispatch. So the
worst case of misreading this signal is one human-run gate that was going to
be recommended anyway. That is the deliberate guard, not an accident of
ordering: never add a row that treats the heading as sufficient to skip the
gate, and if viva ever publishes a real sign-off signal, read that instead
and this note goes away.

**The assessment prints before the recommendation**: the state, then the
evidence line behind each claim — so a misread fails visibly, in front of
the human, before any confirmation is requested.

## Step 2 — Exactly one recommendation

The output is a coach's call, not a menu: **one action**, why (the
evidence lines that determined it), rough cost, the path ahead, then the
confirmation question. The action comes from a closed set: dispatch one of
`/design` `/plan` `/build` `/finish`; recommend the human run a named
studious gate; name a manual step; or state "nothing to dispatch." Never
two options, never a ranked list.

Routing, observed state → the one action:

| Observed state | Next action (exactly one) | Context handed over |
|---|---|---|
| No design doc, no `PLAN.md`; no should-we-build verdict recorded (or the ledger is unreadable) | Recommend the human run `/gate-should-we-build` | The feature idea from conversation |
| Design doc present and signed off (`## Revision History`, or this conversation's own `DESIGNED`); no design-review verdict recorded (or the ledger is unreadable) | Recommend the human run `/gate-design-review` | The doc path |
| Design doc signed off, design-review verdict recorded (or the ledger is unreadable — gap named); no `PLAN.md` | Dispatch `/plan` | The design doc path |
| `PLAN.md` present, no terminal suffixes | Dispatch `/build` | The plan path |
| ` [REPLAN]` suffix on Task N | Name the manual step: revise Task N's checkpoint block by hand, quoting the status-flip commit's reason; after the human says done, reassess and recommend `/build` | The quoted REPLAN reason |
| ` [ESCALATE]` suffix on Task N | Dispatch `/design` in revision mode | The ESCALATE finding (status-flip commit body, quoted) plus the design doc path |
| Every task ` [PASS]`; audit/acceptance not yet recorded (or the ledger is unreadable) | Recommend the human run `/gate-audit` (then `/gate-acceptance`) | The branch name |
| Every task ` [PASS]`; both gates recorded as passed | Dispatch `/finish` | Nothing beyond the invocation — `/finish` reads `PLAN.md` and the evidence folders itself |
| Dated build report exists for this story / branch closed out | Nothing to dispatch — state it and stop | — |

**What the work file adds to this table.** It never overrides a row — the
rows key on repo evidence and that stays the authority. It supplies three
things the repo can't: the feature's slug and title (use them, rather than
inventing a name for the story); corroboration, so a row reached with the
work file agreeing is worth stating as such; and the fact that a handoff
already happened — a `HANDED-OFF` outcome on the `design`, `build`, or
`finish` step means `/work-on` already handed that piece over, so if the repo
shows no result from it, the honest recommendation is the same step again,
named as a resume rather than a fresh start. When a row and the work file
disagree, say both out loud and follow the row.

**When no row matches at all, the work file is what keeps you honest.** The
commonest cause is a design doc that is branch-local by rule and simply not
on this checkout — so `docs/design/*.md` is empty while the work file records
phase `design-review` or later. Do not fall through to the first row and
recommend `/gate-should-we-build`: a recorded decide verdict already rules
that out, and re-recommending a gate the flow passed is the exact
two-navigators-two-answers failure this store-sharing exists to end. Instead
say which signals are missing, name the phase the work file records, and
recommend the step that phase implies — flagged as derived from the work file
rather than from repo evidence, so the human can see which it rests on.

**Rough cost** comes from this fixed vocabulary — order-of-magnitude,
honest about human attention vs. wall clock, never a fabricated number:

- `/design` — one interactive session: 5–9 interview answers plus
  per-section sign-off; the most human attention.
- `/plan` — one session: drafting mostly unattended, then one review card
  per task.
- `/build` — one mostly-unattended session: pauses only at risk-tagged
  tasks and failures; the most wall clock.
- `/finish` — one interactive session: per-item follow-up confirmations
  plus one verdict choice.
- A studious gate — minutes: a single human-run judgment read.
- A REPLAN block revision — minutes of hand editing.

**The path ahead** is one line: the remaining steps of `PRODUCT.md`'s
journey 1 from the recommended action onward (e.g. `/build` →
`/gate-audit` → `/gate-acceptance` → `/finish`).

## Step 3 — Dispatch on confirmation (the Pocock rule)

User-invoked skills orchestrate; model-invoked skills hold reusable
discipline; user-invoked never calls user-invoked — except the coach,
whose sole job is dispatching them one at a time on human confirmation.

- A dispatch happens only after the human's **explicit confirmation in the
  same turn** — never inferred from a prior yes, a stated preference, or
  silence (the same consent bar `/finish`'s harvest step already sets).
- **One confirmation, one dispatch.** Never two skills queued from one
  confirmation; never a dispatched skill's verdict auto-consumed into a
  second dispatch — dispatches are never chained. When the dispatched
  session ends, reassess from fresh repo evidence (Step 1 again, never
  memory) and recommend again — a new confirmation each time.
- **Mechanism**: invoke the target skill by name via the Skill tool,
  passing the routing table's context column as the argument, explicitly —
  never "see conversation above." `/plan` gets the approved design doc's
  path; `/build` gets the plan path; `/design` in revision mode gets the
  quoted ESCALATE finding plus the design doc path.
- **The four build skills are the only dispatch targets.** Studious gates
  are recommended for the human to run, never dispatched — the coach's
  exception to the Pocock rule covers those four and nothing wider.
  viva is never invoked by the coach; the dispatched skills own their own
  viva rounds.
- **A declined recommendation ends the session.** The human says no — the
  coach stops. It does not argue, loop the recommendation, or dispatch
  anything.

## Shortcuts are first-class

A stated shortcut is honored and its skipped steps named, never blocked
(`PRODUCT.md` journey 2, Quick path). The persona who says "small fix,
skip the ceremony" gets: "Quick path: hand-author a single-task `PLAN.md`
in the checkpoint-block format, then I dispatch `/build` — skipping
`/design`, `/gate-design-review`, and `/plan`; `/gate-audit` still applies
after `BUILT`."

## Does no work itself

The coach's tool use is read-only, always: Read/Glob/Grep, `git log`,
`git status`, `command -v`, and `gate-ledger`'s four *read* verbs —
`gate-get`, `status`, `work-list`, `work-get`. Never `work-set`, never
`work-log`, never `record`: sharing `/work-on`'s store means reading it, not
writing it, and a coach that corrected the work file would be doing the work
it exists not to do. It never writes or edits a file (no code, no docs, no
state file of its own), never flips a status, never records a verdict, never
runs a gate, a lint, a test, or a build script, and never commits. Anything that looks like work
is the dispatched skill's job or the human's.

The coach also has **no verdict enum of its own** — it is not a pipeline
judgment point; its closed vocabulary is Step 2's action set. It reads the
other skills' verdicts; it never emits one.

## Degrades gracefully when the ledger can't be read

The gates always exist — they ship in this same plugin, so there is no
state in which one is unavailable and nothing here may reason as if there
were. What can fail is *reading recorded verdicts*: `gate-ledger` off
`PATH` leaves this skill unable to tell a gate that never ran from a gate
that ran and passed.

Resolve that ambiguity toward recommending the gate, never past it. An
unreadable ledger means "unknown," and unknown routes to the gate the same
way "not recorded" does — the human confirms or declines, which is the
whole posture anyway. Name the gap when you do it: "can't read recorded
verdicts (`gate-ledger` not on `PATH`, see `/studious-doctor`) —
recommending `/gate-audit` rather than assuming it passed." Never an error,
never a silent omission, and never a skipped gate.

## Why this shape

"Recommend one action; the human decides. Propose; never apply" — this
skill *is* that principle: one action, confirmation-gated, nothing
applied. "Judgment in the model, mechanics in scripts" — the
recommendation is judgment; nothing here writes or determines pass/fail,
so there is no mechanics to script; the state read reuses grammars scripts
already own (`status-flip`'s `SUFFIX_RE`, gate-ledger's JSON), the same
sanctioned mechanical read of prose already in hand that `/build`'s
steps 1.4–1.5 perform in-model. "Nothing signs off on itself" is
structurally satisfied — the coach produces no artifact to sign off.
"Anti-cleverness tripwire" — no persona name, no resident role, no
ceremony: a session that ends when the recommendation is confirmed,
declined, or answered with "nothing to dispatch."
