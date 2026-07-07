# /work-through — epic-level orchestration

**Date:** 2026-07-07
**Status:** Approved design, pre-implementation

## Problem

Studious walks one story at a time: every gate verdict returns to the user, and the two
handoff pieces (design doc, build) wait on them. That rigor is the product, but it caps
throughput at human pacing. A milestone of 8 stories takes 8 supervised flows even when
6 of them would pass every gate untouched.

Extend Studious one level up: a single command that drives an entire milestone/epic
through the existing gate flow using dispatched agents, escalating to the human only on
the verdicts that genuinely need one.

## Decisions (settled during brainstorming)

| Question | Decision |
|----------|----------|
| Human checkpoints | Exceptions only — plan approval up front, judgment verdicts and epic completion after |
| Epic source | GitHub milestone / epic issue / label, read via `gh`, never written |
| Plan storage | Local gitignored `.studious/epics/<slug>.json` |
| Parallelism | Dependency-DAG parallel, one git worktree per story, epic integration branch |
| Self-correction | Bounded: 2 fix cycles per gate per story for mechanical verdicts; judgment verdicts park immediately |
| Architecture | Prompt-orchestrated command + `gate-ledger` extension (no Workflow tool, no headless fleet in v1) |
| Command surface | One command, `/work-through` — plan piece on first invocation, driver on every later one |

## Posture: what holds, what bends

Holds:

- **Gates unchanged.** Same 5 commands, same verdict vocabulary
  (`reference/gate-vocabulary.md`), same recommend-only reports. The driver cannot
  soften, skip, or reinterpret a gate. Rigor at scale = gates unbypassable in the loop.
- **Lane separation, now at the agent level.** Gate agents never build; worker agents
  never gate; they never share context. Auditors judge the diff blind, as today.
- **GitHub read-only.** No PRs opened, no issues created or modified.
- **State local.** Everything lands in gitignored `.studious/`.
- **Two human-owned moments:** approving the epic plan, and `gh pr create` at the end.

Bends:

- **Auto-advance** — inside an approved epic, PASS verdicts advance without the user.
  `/work-on` keeps its one-piece contract; `/work-through` is a separate, explicitly
  opted-into mode.
- **"Studious never builds"** becomes "Studious never builds in its own lane." Worker
  agents author design docs and code as the dispatched how-layer (Superpowers
  brainstorm/plan/execute when installed, generic agent otherwise). Plan approval is the
  standing authorization.
- **Per-story `decide` is subsumed** by plan approval — approving the decomposition is
  the batched should-we-build. Stories added to an epic later still get a decide pass
  inside the plan-amendment path.

## Command: `/work-through <milestone | epic issue | label>`

Mirrors `/work-on`'s resumable shape. Two modes by state, not by flag:

### First invocation — the plan piece

1. Resolve the argument via `gh` (read-only): milestone → its open issues; epic issue →
   its body, checklist, and linked issues; label → matching open issues.
2. Read PRODUCT.md, DESIGN.md, CLAUDE.md for grounding, as every gate does.
3. Propose a decomposition satisfying `reference/epic-plan-contract.md` (new):
   - **Stories** — title, source issue(s), acceptance criteria, size hint. Splitting or
     merging issues is proposed in the plan, never applied to GitHub.
   - **Dependency edges** — the DAG that drives scheduling.
   - **Gate profile per story** — default full flow (design → design-review → build →
     audit → acceptance); trivial stories may be profiled down to build → audit. Profile
     trimming is proposed by the planner, decided by the user at approval.
   - **Epic pre-mortem register** — cross-story failure modes (integration seams, shared
     schema drift, sequencing risk), written to `docs/studious/premortems/` and verified
     by `premortem-auditor` at the epic finale.
   - **Epic goal statement** — the single sentence the epic-level acceptance gate judges
     against.
4. Stop for approval. The user edits/trims/reorders; approval writes the epic file and
   creates the integration branch name (`epic/<slug>`). Nothing runs before approval.

### Every later invocation — the driver

Constraint that shapes everything: **subagents cannot spawn subagents.** The driver in
the main session is the scheduler; every dispatched agent does one phase of one story,
flat. The driver's context holds only the DAG, phase positions, and verdicts — all
reading, designing, building, auditing happens inside dispatched agents.

Loop per invocation:

1. **Reconcile** — load the epic file and each story's work file; verify against
   evidence exactly as `/work-on` does (verdicts count only at the story branch's HEAD,
   design docs exist on disk, merges actually reached the epic branch). Evidence wins;
   correct the files when they disagree.
2. **Schedule** — runnable = dependencies landed ∧ not parked ∧ under the concurrency
   cap (default 3 concurrent story worktrees; recorded in the epic file, user-settable
   at plan time).
3. **Dispatch** — per runnable (story, phase), in parallel across stories:
   - `design` → worker agent authors a doc satisfying
     `reference/design-doc-contract.md` in the story worktree
   - `design-review` / `audit` / `acceptance` → the existing gate command run as an
     agent, verbatim, recording to the story branch's ledger
   - `build` → worker agent implements from the design doc (Superpowers plan/execute if
     installed; project conventions from CLAUDE.md either way)
4. **Advance** — record outcomes via `gate-ledger`, move phases, merge stories that
   pass acceptance into the epic branch. Merge conflict → one merge-fixer agent attempt
   → else park.
5. **Repeat** from 2 until nothing is runnable, then report.

### Plan amendments

The plan is editable after approval, through the driver — never by hand-editing the
epic file. Asking to drop a story marks it `dropped` and re-evaluates dependents;
asking to add one re-opens the plan piece for just that story (a scoped
should-we-build pass plus user approval of its DAG placement). Both are recorded via
`epic-story-set`.

### Epic finale

When every story is `landed` (or `dropped`): on the integration branch, run
`/gate-audit` against the full epic diff (cross-story integration issues no per-story
audit saw) and `/gate-acceptance` against the epic goal statement, plus the
`premortem-auditor` over the epic register. All pass → status `ready`: recap the full
verdict trail per story, hand the branch to the user for `gh pr create`. The existing
PR-time hook reads the epic branch's ledger and behaves as today.

### Report shape

Every driver invocation ends with a fixed-shape report, exception queue first:

```text
Epic: <slug> — <landed>/<total> landed, <parked> parked, <running-next> runnable.
Needs you:
  - <story>: <gate> returned <verdict> — <one-line reason / what's needed>
Landed this run: <slugs with verdict trails>
Run /work-through when you're ready, or resolve the queue first.
```

## Corrective mechanics

The verdict vocabulary already splits into two types; the driver enforces the split and
never reclassifies:

- **Mechanical** — `REVISE`, `FIX AND RE-AUDIT`, `FIX AND RE-CHECK`: dispatch a fixer
  agent with the gate's findings, then re-run the gate with a **fresh agent** (the
  fixer never grades its own work). Max **2 fix cycles per gate per story**, tracked in
  the epic file; a third failure parks the story.
- **Judgment** — `RETHINK`, `NEEDS DISCUSSION`, `HOLD`, `DEFER`, `DON'T BUILD`: park
  immediately, no retry. These verdicts exist to reach a human; autonomy never absorbs
  them.

**Parking:** story status `parked` with the verdict, the gate's reasoning, and what's
needed. Dependents block; independent siblings continue. Resolution paths, all outside
the driver: answer the question and re-run, edit the design and re-run, ask the driver
to drop the story (see Plan amendments), or take
the story over manually — every story is a valid `/work-on` feature, so takeover needs
zero new machinery.

## State

Two layers, reusing the work-file machinery:

- **Epic file** — `.studious/epics/<slug>.json`: source ref, epic goal, integration
  branch, concurrency cap, pre-mortem path, status
  (`planning | approved | running | ready | done | stopped`), and the story DAG — per
  story: slug, title, source issues, acceptance criteria, deps, gate profile, status
  (`pending | running | parked | landed | dropped`), park reason, per-gate retry
  counters, worktree path.
- **Story work files** — standard `.studious/work/<slug>.json`, schema unchanged.
  Phase lives there and only there; the epic file holds DAG and status. Gate verdicts
  live where they always have: the per-branch gate ledger.

`gate-ledger` grows verbs mirroring the `work-*` family: `epic-set`, `epic-get`,
`epic-list`, `epic-story-set`. Same jq-backed JSON, same rule: nothing reads or writes
these files directly.

## Shipping surface

New files:

- `commands/work-through.md` — the orchestrator prompt
- `reference/epic-plan-contract.md` — what an approvable decomposition must contain
- `skills/run-the-milestone/SKILL.md` — thin shim, conservative triggers ("knock out
  this milestone", "run the whole epic"); must NOT match single-feature or next-piece
  phrasing (that stays with `/work-on` / continue-feature-work)

Changed files:

- `bin/gate-ledger` — the four `epic-*` verbs
- `tests/test_gate_ledger.sh` — cases for each new verb
- `README.md` — section after `/work-on`: "Or have Studious run the whole milestone",
  with an honest token-cost note
- `CONTRIBUTING.md` — the worker-agent lane rule (workers never gate, gates never
  build, no shared context)

## Testing

- Ledger verbs: `bash tests/test_gate_ledger.sh` (new cases), `shellcheck bin/gate-ledger`
- Prompts: `npx -y markdownlint-cli2`, `uv run --no-project python scripts/check_references.py`
- Manifest: `uv run --no-project python scripts/validate_plugin.py`
- End-to-end: manual dry-run against a 2–3 story toy milestone in a sandbox repo before
  release; the orchestrator prompt cannot be unit-tested

## Out of scope (v1)

- GitHub write-back (sub-issue creation, checklist updates) — needs an explicit opt-in
  write mode; revisit after v1 proves out
- Per-story PRs — Studious still never opens PRs
- Workflow-script or headless (`claude -p`) execution backends — the command surface
  and ledger schema stay substrate-agnostic so these can become execution modes later
- Any change to `/work-on`, the 5 gates, the review suite, or CI mode — all ship
  byte-identical

## Risks

- **Context exhaustion in the driver.** Mitigated by flat dispatch (all heavy work in
  agents) and resumability — a fresh session picks up from ledger state exactly like
  `/work-on`.
- **Worker quality without human pacing.** Mitigated by the gates themselves: every
  worker output passes the same gates a human's work would, with fresh-eyes re-audit
  after fixes.
- **Merge-order sensitivity on the epic branch.** Mitigated by DAG ordering, one
  merge-fixer attempt, park-on-conflict, and the finale's full-diff audit.
- **Token cost.** An epic run is 5–10× a supervised flow. README states this plainly;
  the concurrency cap and gate profiles are the levers.

---

## Amendment — 2026-07-07: driver moves to a code substrate

A same-day architecture re-evaluation (`~/Projects/brainstorming/studious-reevaluation-2026-07-07.md`)
reversed the "prompt-orchestrated command, no Workflow tool in v1" decision before
release: state machines held in prose develop dead zones the model fills by
improvising — the v1 branch's own final review found exactly that class (a merge
trigger that missed trimmed gate profiles; retry counters with no reset; no un-park
transition). The governing rule is now: **code owns bookkeeping; prompts own
judgment.**

What changed:

- **Primary driver = a Workflow script** (`workflows/epic-driver.js`). The command
  reconciles state from ledger + evidence, assembles it as `args`, invokes the script,
  and renders its returned report. DAG scheduling, the concurrency cap, the 2-fix-cycle
  caps, and merge order live in plain JS; the script's in-memory DAG is a working copy
  — every state mutation is written by the agent that caused it, via `gate-ledger`, so
  crash recovery stays reconcile-and-re-run.
- **The v1 prompt driver survives as the documented fallback** for environments
  without the Workflow tool, corrected to these semantics (below) so the modes stay
  interchangeable mid-epic.
- **Corrected semantics, both modes** (from the v1 final review): stories merge when
  their **final profiled gate** returns its proceed token (not only on SHIP);
  `gate-ledger` anchors all `.studious/` state to the **main working tree** via the
  git common dir, so verdicts recorded inside story worktrees share one store;
  un-parking is explicit (`epic-story-set --status pending --reset-retry <gate>`),
  never driver-initiated; the epic branch is created from the **default branch**;
  story branches are `epic/<slug>--<story>` (a nested name can't coexist with the
  `epic/<slug>` ref); the `__epic` worktree is removed once the epic reaches `ready`.
- **Gate fan-out inside the script:** `agent()` subagents can't spawn subagents, so
  the script dispatches the audit gate's auditors itself as parallel agents (via the
  plugin's agent definitions, keeping their pinned models) plus a verdict-compiler
  applying `commands/gate-audit.md`'s rubric.
- **New `reference/worker-contract.md`** — what a dispatched worker receives and what
  it must return (committed work, summary, evidence; "done" without artifacts is not
  done). The contract, not Superpowers, is normative; PRODUCT.md's "not building"
  entry now carries the bounded epic-driver exception.
