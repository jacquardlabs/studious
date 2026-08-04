# Studious

[![CI](https://github.com/jacquardlabs/studious/actions/workflows/ci.yml/badge.svg)](https://github.com/jacquardlabs/studious/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jacquardlabs/studious)](https://github.com/jacquardlabs/studious/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A product development workflow for Claude Code, from [Jacquard Labs](https://github.com/jacquardlabs).

## Why

Claude Code made building cheap. That moved the bottleneck. The hard part is no longer
*can we build it*. It's *should we build it, and did we build it right*.

Studious adds that judgment back as seven doors, named for the stages you already know from
kanban, Scrum, XP, and Shape Up. It owns the judgment — what to work on, whether a design
serves users, whether the implementation delivers, whether the codebase stays healthy. It
does not own the building: that enters through a contract
(`reference/worker-contract.md` — story brief in, implementation and evidence out). A build
loop that satisfies it ships in the box, and so does any other executor you prefer: you by
hand, a dispatched agent, or [Superpowers](https://github.com/obra/superpowers). No judge
knows or cares which one produced the branch, and CI enforces that.

## The seven doors

| Door | What it's for | Stage it names |
|---|---|---|
| `/bet [idea \| issue \| milestone]` | Choose the work and set its appetite | betting table · ready · refinement |
| `/shape [idea]` | Define it before building | shaping · spike |
| `/build` | Plan, then build | in progress · sprint · TDD |
| `/review` | Judge it — design, work, or delivery | review column · sprint review |
| `/ship` | Deliver and close out | done · increment · small releases |
| `/next [anything]` | The standup question, at any scale | standup · pull · hill chart |
| `/retro [area]` | The periodic look-back | retrospective · kaizen · cool-down |

Plus two you'll run rarely: `/setup` (first-time scaffolding) and `/studious:doctor`
(install diagnostics — namespaced, because Claude Code ships its own `/doctor`).

Every door also answers to its namespaced form, `/studious:<door>`. Reach for it when a
bare name collides with a Claude Code built-in or another plugin — the namespaced form is
always unambiguous.

**The flow is scale-invariant.** A bet's scope may be one story, a list of stories, or a
whole milestone — same doors, same order, every time. Scope changes how many stories a bet
contains and how much runs unattended versus supervised. It never changes which doors
exist, or where the flow enters and exits.

**No door is mandatory, only default.** Skip `/bet` and you have no appetite and no decision
record — everything else still runs, and position still derives from repo evidence. Use
judgment about which checks the risk warrants; that judgment is yours.

## Quick start

Via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install studious@jacquardlabs-marketplace
```

That also installs [viva](https://github.com/jacquardlabs/viva), a declared dependency:
`/shape` and `/build` drive it for their human sign-off rounds.

Then, in any project:

```
/setup
```

This creates your context documents — PRODUCT.md and DESIGN.md, extracted from the codebase
as it actually is — scaffolds the `docs/studious/` report directories, and wires the
workflow into CLAUDE.md. Review PRODUCT.md first: the extraction is evidence-based, but your
product principles and your "not building" list need your voice.

Then stop reading and run one command:

```
/next [idea, issue, or milestone]
```

`/next` is the only door you have to remember. It reads where the work stands, names the
next door, and runs it on your word.

## How it works

```
/bet     →  scores the idea, ranks it against the backlog, sets the appetite
   ↓
/shape   →  interview, drafted design doc, viva sign-off per section
   ↓
/review  →  design episode; writes the pre-mortem register on a pass
   ↓
/build   →  plans, then builds — fresh executor per task, script-verified, evidence captured
   ↓
/review  →  work episode; up to 13 specialist lanes, plus criteria conformance
   ↓
/review --delivery  →  delivery episode; does this deliver what the bet promised?
   ↓
/ship    →  evidence table, follow-ups, build report, then the PR is yours
```

`/next` walks that sequence for you, one piece per invocation, and never auto-advances.
Position lives in local, gitignored `.studious/` state, so the flow survives across sessions
and picks up where the work actually stands — including doors you ran by hand.

At milestone scale, the same `/next` proposes a story plan (dependency order, acceptance
criteria, per-story gate profile, an epic-level pre-mortem), interviews you once for the
whole epic, shows you what it will cost, and stops for approval. Nothing runs before you
approve. Then dispatched agents drive the unattended stories in parallel worktrees, and hand
back the ones a judge can't verify mechanically. Full contract:
[`reference/epic-orchestration.md`](reference/epic-orchestration.md).

### Episodes, not re-runs

`/review` opens an **episode**: one bounded run of judgment on a branch, at one sha, with at
most two rounds and exactly one terminal verdict. A fix re-enters the *same* episode,
narrowed to the lanes that blocked — so you see `round 2 of 2, 3 findings open, 1 carried`
instead of an unexplained re-run. Findings persist across rounds in a ledger, so a later
round can't re-litigate what an earlier one settled. The round cap lives in code
(`bin/gate-ledger`), never in a prompt.

Bare `/review` picks its episode from repo state: a design doc with no built diff opens the
design episode, a built diff opens the work episode. `--delivery` is always explicit, because
delivery is a boundary someone decides they've reached, never one inferred from a diff. When
the signals disagree, it stops and says so rather than guessing.

Narrow it when the risk doesn't warrant the fan-out: `/review --lane security` or
`/review --conformance` convenes one lane at one lane's price.

### What the work episode checks

Security, code quality, docs, architecture, and test adequacy always run, alongside a
criteria-conformance review against the story's own stated acceptance criteria. Then, by what
the changeset touches: UX, frontend, and accessibility on a web surface; infrastructure on
IaC/container/CI files; operability on runtime code; dependencies on manifest or lockfile
changes; prompts on agent/command/skill definitions. If the design episode recorded a
pre-mortem register, a dedicated auditor checks each predicted failure mode against what
shipped — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 13 lanes, each
staying in its own.

When you run `gh pr create`, a PR-time hook reads the recorded verdicts and names any that
never ran, ran on an older commit, or didn't pass. It's a reminder, not a block.

### Natural language works too

"Should we build this?" routes to `/bet`. "Review this design" or "audit this branch" routes
to `/review`. "What's next" or "keep going" routes to `/next`. Triggers are deliberately
conservative, so you'll still reach for the doors directly most of the time.

## The build loop

Two steps — writing the design and writing the code — are what Studious judges but doesn't
perform. It ships a route through both. Use it, or don't; the judges can't tell.

- **`/shape`** inventories your context docs and the code the change touches, runs one batch
  interview of 5–9 questions (forks as 2–3 options, one recommended), drafts the design doc
  section by section, and holds every section at a viva sign-off round in the browser.
  Reports `DESIGNED`, `NEEDS RESEARCH`, or `REVISED`.
- **`/build`** plans, then builds. Planning turns the design doc into a `PLAN.md` — a
  dependency spine, 3–8 calibrated tasks, a checkpoint block each — that has to pass
  `scripts/plan-lint` and a viva round before any code is written. Building works that plan
  one task at a time in a fresh, isolated executor, verifies each by running the task's own
  commands, and captures the output as evidence. Status flips are written by scripts, never
  by the model, and load-bearing tasks get a fresh inspector judging exactly three things:
  test self-dealing, contract match, technicality gaming. Reports `BUILT`, `PAUSED`, or
  `ESCALATED`, and never auto-continues past a pause.
- **`/ship`** closes out a `BUILT` branch: an evidence table mapping each done-means item to
  how it was verified, follow-ups filed only on per-item confirmation, proposed (never
  applied) patches to your context docs, and a dated build report. Reports `MERGE`, `PR`,
  `KEEP`, or `DISCARD`. `/ship --handback` is the PR-less variant a dispatched worker uses.

**No judge requires any of this.** `scripts/check_gate_independence.py` fails CI if a judge
door, specialist agent, driver, hook, or the ledger so much as invokes a producer door or
reads a producer's private artifact. Its guarded surface is derived from
[`reference/personas.md`](reference/personas.md), so a renamed door can't fall off it
silently. What a judge may rely on is `reference/evidence-format.md`, which any executor can
satisfy.

## Keeping the project healthy

Separate from the feature flow: `/retro` runs periodic reviews against main, not feature
branches. Bare `/retro` dispatches all 7 review agents in parallel and compiles a master
summary — cross-referenced findings, a prioritized action plan, and proposed context-doc
updates for your approval. Metrics are captured each run for trend tracking.

| Area | What it checks | Cadence |
|------|----------------|---------|
| `/retro codebase` | Architecture coherence, tech debt, dependencies, test gaps | Weekly or pre-milestone |
| `/retro interface` | Cross-surface consistency, design drift, accessibility, interface code | Monthly or post-UI work |
| `/retro architecture` | Module boundaries, complexity, evolution readiness | Quarterly |
| `/retro product` | PRODUCT.md accuracy, persona drift, scope creep | Monthly |
| `/retro security` | Whole-repo vulnerability posture, secrets in history, config posture | Monthly |
| `/retro readme` | Stale claims, broken commands, voice drift | After a release |
| `/retro prompts` | Trigger coverage, contract alignment, duplication, injection posture | Monthly |
| `/retro backlog` | Open issues that are resolved, obsolete, or duplicated | After a review cycle |
| `/retro outcomes` | Shipped merges graded against the fixes and reverts that followed | Quarterly |

Every mode is recommend-only. It writes reports; it never writes code, closes an issue, or
records a verdict.

## Context documents

Everything reads from 3 files in your project root. `/setup` creates them; you maintain them.
Refresh one on its own with `/setup extract-product` or `/setup extract-design`.

| Document | What it holds | Updated by |
|----------|---------------|------------|
| PRODUCT.md | Personas, principles, known problems, "not building" list | You + `/retro product` |
| DESIGN.md | Interface conventions per surface — web UI, CLI, TUI, API, or report | You + `/retro interface` |
| CLAUDE.md | Technical conventions, workflow reference | You + `/retro architecture` |

Reviews propose updates to these docs. They never apply them. If a doc goes stale, the
reviews tell you. That's the point.

## CI mode (optional)

`.github/workflows/gate-audit-pr.yml` runs the work episode non-interactively against a PR
and posts the report as a PR comment — the same lane fan-out you'd get locally. It ships
**dormant** (manual `workflow_dispatch` only): pick a PR, run the workflow from the Actions
tab with that PR's number as input.

1. Add `ANTHROPIC_API_KEY` as a repository secret (Settings → Secrets and variables →
   Actions). Without it, the job fails at the headless-run step.
2. Test it manually against a real, non-draft, same-repo PR and read the comment it posts
   before trusting it further.
3. To run it automatically on every PR, change the workflow's `on:` block from
   `workflow_dispatch` to `pull_request: types: [opened, synchronize, reopened,
   ready_for_review]`, and swap every `inputs.pr_number` reference for
   `github.event.pull_request.number`.

It refuses draft PRs and fork PRs (no repository secrets reach fork-triggered runs, which
keeps the agent's Bash access scoped to contributors who already have write access), and
skips diffs over 40 changed files to bound the fan-out's cost.

## Works well with

- [viva](https://github.com/jacquardlabs/viva) — a declared dependency, installed
  automatically. `/shape` and `/build` drive it for their sign-off rounds, through viva's
  published headless contract. It stays a separate repo because that contract is versioned
  and tested, not a format convention.
- [Superpowers](https://github.com/obra/superpowers) — an optional alternative to the
  built-in build loop. Any executor satisfying `reference/worker-contract.md` works.
- GitHub Issues — `/bet` and `/retro backlog` read your tracker via the `gh` CLI.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report issues, propose changes, and the
structure conventions for agents, commands, and skills. The door surface itself is data:
[`reference/personas.md`](reference/personas.md) is the charter, and both the CI check and
these docs derive from it.

## License

MIT — see [LICENSE](LICENSE).
