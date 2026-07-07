# Initiative altitude — design record (formerly Brigade)

> **Provenance:** moved from `jacquardlabs/brigade` (archived 2026-07-07) under the
> repo-boundary rule in CLAUDE.md — layers of the delivery discipline are entrypoints
> of this repo, not separate products. The entry gate below is unchanged: this
> altitude gets built here, as an entrypoint, if and when it fires.

**Status:** founding vision · **Date:** 2026-06-20

Brigade orchestrates initiative-scale delivery: it takes a PRD, gates whether it's worth building and whether it's ready to decompose, breaks it into independently-executable stories, delegates each one downward, observes the parallel execution, and gates acceptance of the integrated whole.

The name comes from the brigade de cuisine and from military brigades — coordinated units executing under command, converging at one point where quality is gated and the parts become a coherent whole. **The name stays at the door. The metaphor does not walk into the design** — roles and components carry plain, functional names.

## The thesis

**Brigade is studious's feature-gate loop hoisted one altitude up.** It is not a different *kind* of system from [studious](https://github.com/jacquardlabs/studious) (delivery vs. judgment). It is the same loop — *should-we-build → decompose → delegate → observe → gate acceptance* — instantiated at the initiative altitude instead of the story altitude.

The gate loop is **scale-invariant**. The orchestration around it is **additive** — three capabilities exist at the initiative altitude that have no story-level analog (decomposition, the observe/coordinate runtime, integration). The recursion could extend a third tier up (a portfolio loop over initiatives) without changing the shape.

## Where it sits

```
Brigade      initiative altitude — gate the initiative, decompose into stories,
   │         delegate, observe, gate integrated acceptance
   │  delegates each story to … (agnostic: studious, or a swarm of humans)
   ▼
studious     story altitude — re-gate scope, gate design, audit, gate acceptance
   │  delegates the build to … (agnostic: Superpowers, or a human)
   ▼
Superpowers  build the story — brainstorm, plan, TDD, execute
```

The agnosticism recurses. studious does not care whether Superpowers or a human builds a story. **Brigade does not care whether studious-then-Superpowers or a swarm of humans delivers a feature.** Each layer hands down a scoped unit of work plus acceptance criteria and gates what comes back. The shared abstraction between every pair of layers is the same: *here is a bounded unit of work and what "done" means — execute it however you like and report; I will gate the result.*

Brigade is a **separate product** from studious, for the same reason studious is separate from Superpowers: folding it in would widen studious's surface and break its identity ("we own the what and the whether, not the how"). Brigade depends on studious the way studious works well with Superpowers — by delegation, not absorption.

## Scale-invariant gates, additive orchestration

**Symmetric with studious (the gate loop):** should-we-build, gate acceptance, the no-yes-man stance, decisive verdicts, judgment grounded in product context docs.

**Additive (no story-level analog):**

1. **Decomposition** — studious never decomposes; it gates one story. Brigade must produce the dependency DAG and freeze the interface contracts (seams) between stories.
2. **The observe/coordinate runtime** — andon, mission control, dependency unblocking. studious fires a gate and returns; Brigade runs a long-lived loop watching N parallel delegations.
3. **Integration / rollup acceptance** — initiative acceptance is a rollup of story acceptances *plus* emergent cross-cutting behavior, not a bigger version of one gate.

## The gate sequence

1. **Should we build this initiative?** — initiative-scope judgment. Unlike studious's feature gate, it permits multiple personas, *encourages* phasing (what's the first milestone that delivers standalone value?), weighs whole-initiative cost against the portfolio of known problems, and can return **SPLIT** (this is several initiatives stapled together). Verdicts: **BUILD / BUILD SMALLER (phase it) / SPLIT / DEFER / DON'T BUILD**.

2. **Do we have enough to break this down and execute it?** — a readiness + decomposition gate. Is the PRD complete enough, and does a clean decomposition into independently-executable stories exist with real dependencies and clean seams? Verdicts: **READY / NEEDS MORE (enrich the PRD) / SPLIT / NOT YET**. This is the andon *before* any agent is spawned — cheap to fail here, expensive to fail later.

3. **Delegate each story downward.** studious re-gates the story's scope with its existing feature-scoped should-we-build, then drives the build (or a human does).

4. **Gate integrated acceptance.** Does the integrated whole satisfy the Director's outcome contract — including emergent behavior no single story owns?

### The double-gate cross-check

Brigade decomposes and *believes* its stories are right-sized. studious then **independently** re-gates each story's scope. If studious returns BUILD SMALLER — the story is still too big — that is not merely a story-level verdict. **It is feedback that Brigade's decomposition was too coarse** — an andon pull from below. The lower altitude validates the upper altitude's output. Two independent gate loops keep each other honest. This is a safety property, not a tidiness one.

## The org

Plain names; the kitchen/military metaphor does not leak in.

- **Director** (PM role) — owns the PRD. Runs the initiative should-we-build, writes the **outcome contract** (the concrete statements that must be true to call the initiative done), and owns final acceptance. The human's primary counterpart.
- **Lead** (tech-lead role) — owns decomposition into the dependency DAG, freezes interface contracts between stories, schedules along the critical path, and owns integration. Plays supervisor — but as a role in the org, not a separate fragile process. Submits its decomposition to gate #2.
- **Pods** (one per story) — builder + reviewer + integrator, working in an isolated git worktree against frozen contracts. The builder delegates downward (studious → Superpowers, or a human). Brigade dispatches; it does not reimplement building.
- **QA fabric** — studious's existing auditors and acceptance gate, *called down into studious* per story and at integration. Not owned by Brigade.

## Control flow — blackboard substrate, wave rhythm

State lives on disk (see schema). Director gate → Lead decomposes → readiness/decomposition gate → execution: the scheduler dispatches **every story whose dependencies are met and whose contracts are frozen**, pods run in parallel worktrees, each finishes → per-story audit → merge to the integration branch → dependents unblock and dispatch *as soon as they're eligible* (continuous flow, not a hard barrier).

The **human sees execution grouped as waves** and approves at gate boundaries; between gates it runs autonomous. Kill and resume from blackboard state at any point.

## The andon protocol

A single `andon` record (flag, reason, puller, scope, proposed resolution) in the blackboard. Modeled on the Toyota andon cord: the line runs itself *precisely because* anyone can stop it.

- **Who pulls:** the human (mission-control button); any pod (ambiguous contract, repeated audit failure, unexpected blocker); any studious gate (a blocking verdict it can't auto-remediate — including "story too big," which means re-decompose); the budget guard (cost ceiling hit).
- **Effect:** the scheduler stops dispatching; in-flight pods checkpoint; the run parks **HALTED** with the reason and a proposed resolution, surfaced to the human.
- **Resolutions:** amend the PRD/contract and re-plan the affected subtree, re-spawn the failed story, narrow scope, or abort. Human — or Director, if delegated — clears the cord.
- **Key property:** a pull is *cheap and expected*, not a failure. It is the mechanism that makes autonomy safe.

## Blackboard schema (shared state = the substrate)

`docs/brigade/initiatives/<id>/`:

| File | Holds |
|------|-------|
| `prd.md` | The input, frozen at kickoff, plus an amendments log |
| `outcome.md` | The Director's outcome contract |
| `dag.json` | Stories, dependencies, frozen interface contracts, per-story status (`pending│eligible│building│auditing│merged│failed`), owning pod, worktree ref, gate verdicts, cost |
| `andon.json` | The cord state |
| `ledger.jsonl` | Append-only event log: every dispatch, verdict, merge, andon pull |

`ledger.jsonl` is studious's traceability concept ([studious #31](https://github.com/jacquardlabs/studious/issues/31)) realized at initiative scale. It is the single source for both resume and mission control — no separate state to keep in sync.

## Mission control (the visualization layer)

A local web view — same pattern as the brainstorming visual companion / viva server — that is a **read-only render of the blackboard**:

- The **DAG as a live graph** — stories colored by status, critical path highlighted, blockers flagged.
- **Pod cards** — what each is building, current gate, cost burned.
- **Andon banner** — current state, one-click human pull and resolve.
- **Burn meter** against the budget ceiling, and a **gate timeline** of every verdict studious returned.

## Failure, recovery, cost

- Story fails audit → bounded remediation attempts → still failing → andon.
- Semantic integration conflict despite frozen contracts → integrator attempts reconciliation → can't → andon.
- Per-initiative budget ceiling; per-wave soft checkpoint; budget guard pulls the cord at the ceiling. **Gates double as cost off-ramps.**
- Any crash → resume from blackboard.

## What Brigade is NOT

- It does **not** build. It delegates building downward and stays method-agnostic.
- It does **not** judge story scope. studious re-gates each story; Brigade only judges at the initiative altitude.
- It does **not** require studious. Any executor that accepts a scoped unit of work and returns a gated result satisfies the contract — studious is the reference executor, a human swarm is a valid one.
- It does **not** modify studious. studious ships unchanged; Brigade reuses its gates and its traceability concept by delegation.

## Smallest version worth shipping (the kernel)

Apply studious's own ethos to Brigade itself — don't build the full org first. The kernel that proves the thesis:

- **2 roles** — Director + Lead. Pods are single agents, not full pods.
- **The two initiative gates** — should-we-build (initiative scope) and the readiness/decomposition gate. Both are independently useful to a human sizing up an epic by hand, *before* any swarm exists.
- **Blackboard** with `dag.json` + `ledger.jsonl`. Status via CLI print — **no UI yet**.
- **Andon as a manual human halt only** (agent/gate-pulled cord = phase 2).
- **One real initiative end-to-end as dogfood** — e.g., drive a small multi-issue studious initiative through Brigade.

This proves: PRD → judged decomposition → coordinated multi-story execution → integrated acceptance. Full pods, live mission control, agent-pulled andon, semantic-conflict reconciliation, and the cost dial all layer on after.

## Open questions

- Command surface — `/brigade <prd>` vs. a verb. Naming of the readiness gate.
- How pods map to worktrees, and how the integration branch is structured.
- Semantic-conflict detection beyond git — what signal catches two stories diverging despite frozen contracts.
- Where mission control's server lives and how it's launched.
- Whether the Director can be delegated authority to clear andon pulls, and under what bounds.
- Packaging as a Claude Code plugin (`brigade@jacquardlabs`) and its dependency declaration on studious.

## Relationship to studious

Brigade requires **zero changes to studious**. The initiative-scope gates live in Brigade (their altitude). studious's existing feature-scoped should-we-build is already correctly scoped for the stories Brigade emits. The only studious roadmap item Brigade reuses is traceability ([#31](https://github.com/jacquardlabs/studious/issues/31)), whose ledger concept becomes Brigade's `ledger.jsonl`.

---

## Amendment 001 — 2026-07-07: the kernel shipped through studious; Brigade narrows to the initiative altitude

**Status:** adopted. **Trigger:** the studious `/work-through` re-evaluation of 2026-07-07.

**What happened.** studious's `/work-through` (designed and implemented 2026-07-07, `feat/work-through`) is this document's "smallest version worth shipping," built inside studious: the epic-plan contract is the Lead's decomposition plus the readiness gate; plan approval is the batched should-we-build; DAG-parallel story worktrees are the pods and wave rhythm; parking is a manual andon; the epic file plus `gate-ledger` is the blackboard (`dag.json` + `ledger.jsonl`); the merge-fixer is the integrator; the epic finale (full-diff audit + goal-statement acceptance + premortem verification) is integrated acceptance.

**Superseded claims.** "Brigade requires zero changes to studious" and "Brigade does not modify studious" no longer hold. The kernel ships inside studious deliberately — that is where marketplace distribution and the gate ledger live — with the driver re-implemented on a code substrate (Workflow script; the governing rule: code owns bookkeeping, prompts own judgment) and a state schema designed to lift out into Brigade cleanly if and when this altitude is built.

**Brigade's remaining, unduplicated purpose — the initiative altitude proper.** Everything `/work-through` does not and should not do:

- **Initiative should-we-build** — multiple personas permitted, phasing encouraged, the **SPLIT** verdict ("this is several initiatives stapled together").
- **Outcome contracts** — the Director's concrete done-statements that initiative acceptance judges, above any epic's goal statement.
- **Readiness/decomposition gate across epics** — seams and interface contracts *between* epics, not between stories.
- **Multi-epic coordination** — critical path across epics, cross-epic interference, sequencing, and the budget guard.
- **Agent- and gate-pulled andon** (work-through's parking is human-resolved only) and **mission control** (the read-only blackboard render).

One sentence: `/work-through` runs one epic; Brigade runs the portfolio of epics under one PRD.

**Entry gate (evidence, not dates).** Brigade moves from design to build only when a real initiative spans ≥ 2 epics/milestones and per-epic `/work-through` demonstrably leaves cross-epic sequencing, seam drift, or budget unmanaged — or an external ask arrives. Until then this repo stays design-only.

**The honest alternative, recorded.** If the initiative altitude never materializes, Brigade retires quietly. The kernel already lives in studious; nothing is stranded, and this document remains the dated record that the recursion was designed before it was needed.
