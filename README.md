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

What moves through those doors is a **bet**: one thing you've decided is worth building,
plus what you're willing to spend on it. Its scope may be a single story or a whole
milestone — the doors don't change. [Full definition below](#bets).

## The seven doors

| Door | What it's for | Stage it names |
|---|---|---|
| `/bet [idea \| issue \| milestone]` | Choose the work and set its appetite | betting table · ready · refinement |
| `/shape [idea]` | Define it before building | shaping · spike |
| `/build` | Plan, then build | in progress · sprint · TDD |
| `/review` | Judge it — design or work, and whether it delivers | review column · sprint review |
| `/ship` | Deliver and close out | done · increment · small releases |
| `/next [anything]` | The standup question, at any scale | standup · pull · hill chart |
| `/health [area]` | The periodic inspection | health check · standing review |
| `/retro [outcomes]` | The periodic look-back | retrospective · kaizen · cool-down |

Plus two you'll run rarely: `/setup` (first-time scaffolding) and `/studious:doctor`
(install diagnostics — namespaced, because Claude Code ships its own `/doctor`).

Every door also answers to its namespaced form, `/studious:<door>`. Reach for it when a
bare name collides with a Claude Code built-in or another plugin — the namespaced form is
always unambiguous.

**The flow is the same at every scale.** A bet's scope may be one story, a list of stories,
or a whole milestone — same doors, same order, every time. Scope changes how many stories
a bet contains. It never changes which doors exist, or where the flow enters and exits.

**No door is mandatory, only default.** Skip `/bet` and you have no appetite and no decision
record — everything else still runs, and position still derives from repo evidence. Use
judgment about which checks the risk warrants; that judgment is yours.

**Plain language works too.** "Should we build this?" routes to `/bet`. "Review this design"
or "audit this branch" routes to `/review`. "What's next" or "keep going" routes to `/next`.
Triggers are deliberately conservative, so you'll still reach for the doors directly most of
the time.

## Quick start

Via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install studious@jacquardlabs-marketplace
```

That also installs the two declared dependencies: [viva](https://github.com/jacquardlabs/viva),
which `/shape` and `/build` drive for their human sign-off rounds, and
[gauntlet](https://github.com/jacquardlabs/gauntlet), whose judges `/review` and `/health`
dispatch.

Then, in any project:

```
/setup
```

This creates your context documents — PRODUCT.md and DESIGN.md, extracted from the codebase
as it actually is — scaffolds the `docs/studious/` report directories, and wires the
workflow into CLAUDE.md. If [exorcist](https://github.com/jacquardlabs/exorcist) is
installed, it also offers to install the ward, so every executor builds under the same
simplification rules the judges hold it to. Review PRODUCT.md first: the extraction is evidence-based, but your
product principles and your "not building" list need your voice.

Then stop reading and run one command:

```
/next [idea, issue, or milestone]
```

`/next` is the only door you have to remember. It reads where the work stands, names the
next door, and runs it on your word.

---

*Everything below is reference. Come back to it when you want the mechanism.*

## Bets

A **bet** is what moves through the doors: one thing you've decided is worth building, plus
what you're willing to spend on it. `/bet` opens it, `/ship` closes it, and every door
between judges the same bet.

- **Scope** — one story, a list of stories, or a whole milestone. Scope changes how many
  stories a bet contains, never which doors exist: a list is its stories, run one at a
  time in one session with you present.
- **Appetite** — a budget, not an estimate, and your number rather than a model's guess.
- **A bet with no appetite is still a bet.** It runs unpriced; nothing refuses to proceed.

### When a bet is missed

**Spent the appetite.** Studious borrows Shape Up's vocabulary but not its circuit breaker:
a spent appetite is a number you notice, not a stop the tool enforces. Worth knowing before
you set a tight one: **an appetite set too small doesn't fail loudly.** The work quietly
scopes down instead, which reads as a weaker result rather than as a ceiling being hit.
Setting one anyway is a legitimate choice — it's a choice to accept a degraded result, not
a smaller one.

**Didn't deliver.** The other way to miss is to spend the appetite and not deliver what the
bet promised. The work episode's product lane asks exactly that of every built branch —
against the story's criteria and PRODUCT.md's journeys — so there is no separate delivery
episode to remember to run.

**You are the ceiling.** Nothing runs unsupervised: `/bet` records the verdict, and the
appetite is a number you hold yourself.

## The flow

```
/bet     →  scores the idea, ranks it against the backlog, sets the appetite
   ↓
/build   →  plans from the issue (or a design doc), stamped task by task in viva, then
            builds — fresh executor per task, script-verified, evidence captured — then
            convenes /review's work episode itself: up to 13 specialist lanes, plus
            product acceptance: does this deliver what the bet promised?
            --candidates 2|3 builds the plan in parallel, ranks mechanically, and you
            pick between two finalists
   ↓
/ship    →  evidence table, follow-ups, build report; the PR is yours

/shape is off the default path: ask for it, or /build asks for it with DESIGN GAP —
interview, drafted design doc, viva sign-off per section, then /review's design episode.
```

`/next` walks that sequence for you, one piece per invocation, and never auto-advances.
Position lives in local, gitignored `.studious/` state, so the flow survives across sessions
and picks up where the work actually stands — including doors you ran by hand.

**At milestone scale,** `/next <milestone>` expands it to its open issues, proposes an
order, and runs each story through the same flow, one at a time, naming the next when one
reaches `done`.

## The build loop

Two steps — writing the design and writing the code — are what Studious judges but doesn't
perform. It ships a route through both. Use it, or don't; the judges can't tell.

- **`/shape`** inventories your context docs and the code the change touches, runs one batch
  interview of 5–9 questions (forks as 2–3 options, one recommended), drafts the design doc
  section by section, and holds every section at a viva sign-off round in the browser.
  Once every section is signed off, it convenes `/review`'s design episode itself — the
  verdict is always `/review`'s, `/shape` never writes one. Reports `DESIGNED`,
  `NEEDS RESEARCH`, or `REVISED`, plus the convened episode's own `PROCEED TO PLAN`,
  `REVISE`, or `RETHINK`.
- **`/build`** plans, then builds. Planning turns the design doc into a `PLAN.md` — a
  dependency spine, 3–8 calibrated tasks, a checkpoint block each — that has to pass
  `scripts/plan-lint` and a viva round before any code is written. Building works that plan
  one task at a time in a fresh, isolated executor, verifies each by running the task's own
  commands, and captures the output as evidence. Status flips are written by scripts, never
  by the model, and load-bearing tasks get a fresh inspector judging exactly three things:
  test self-dealing, contract match, technicality gaming. After the last task passes, an
  exorcist pass strips what no criterion asked for, the scripts re-verify, and one
  `exorcise:` commit lands (skipped with a note when exorcist is not installed). It then
  convenes `/review`'s work episode itself — the verdict is always `/review`'s, `/build`
  never writes one — dispatching a fresh, scoped fix executor and re-convening once on its own
  `FIX AND RE-REVIEW` before handing an unresolved fix cycle back. Reports `BUILT`,
  `PAUSED`, or `ESCALATED`, plus the convened episode's own `PASS`, `FIX AND RE-REVIEW`, or
  `NEEDS DISCUSSION`, and never auto-continues past a pause.
- **`/ship`** closes out a `BUILT` branch: an evidence table mapping each done-means item to
  how it was verified, follow-ups filed only on per-item confirmation, proposed (never
  applied) patches to your context docs, and a dated build report. Reports `MERGE`, `PR`,
  `KEEP`, or `DISCARD`. `/ship --handback` is the PR-less variant a dispatched worker uses.

**No judge requires any of this.** `scripts/check_gate_independence.py` fails CI if a judge
door, specialist agent, hook, or the ledger so much as invokes a producer door or
reads a producer's private artifact. Its guarded surface is derived from
[`reference/personas.md`](reference/personas.md), so a renamed door can't fall off it
silently. What a judge may rely on is `reference/evidence-format.md`, which any executor can
satisfy.

## Episodes, not re-runs

`/review` opens an **episode**: one bounded run of judgment on a branch, at one sha, with at
most two rounds and exactly one terminal verdict. A fix re-enters the *same* episode,
narrowed to the lanes that blocked — so you see `round 2 of 2, 3 findings open, 1 carried`
instead of an unexplained re-run. Findings persist across rounds in a ledger, so a later
round can't re-litigate what an earlier one settled. The round cap lives in code
(`bin/gate-ledger`), never in a prompt.

Bare `/review` picks its episode from repo state: a design doc with no built diff opens the
design episode, a built diff opens the work episode. When the signals disagree, it stops and
says so rather than guessing.

Narrow it when the risk doesn't warrant the fan-out: `/review --lane security` or
`/review --conformance` convenes one lane at one lane's price.

### What the work episode checks

Security, code quality, docs, architecture, and test adequacy always run, alongside a
product-acceptance review against the story's own criteria and PRODUCT.md's journeys. Then, by what
the changeset touches: UX, frontend, and accessibility on a web surface; infrastructure on
IaC/container/CI files; operability on runtime code; dependencies on manifest or lockfile
changes; prompts on agent/command/skill definitions. If the design episode recorded a
pre-mortem register, a dedicated auditor checks each predicted failure mode against what
shipped — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 13 lanes, each
staying in its own.

## Hooks

Two, both silent unless they have something to say, both declared in `hooks/hooks.json`:

| Hook | Event | What it does |
|---|---|---|
| `hooks/evidence-capture.sh` | `PostToolUse` and `PostToolUseFailure` on `Bash` | While a story is armed, appends each verification command's record to the branch's evidence log (`reference/evidence-format.md`). No-op when nothing is armed. |
| `hooks/session-start.sh` | `SessionStart` on `startup` and `resume` (never `/clear`, `/compact`, or a fork) | If a feature is in flight, prints a one-to-three-line heads-up — counts and the most-recently-updated item, never the full list — so the session opens knowing what `/next` would resume. |

Neither blocks a tool call, asks a question, or writes outside `.studious/`.

## Where your state lives

Two directories, one committed and one not, plus `docs/exorcist/` when you run
`/health simplify` (exorcist's own register path), and the gitignored `docs/design/` a
`/shape` doc and its pre-mortem register live in until `/ship` removes them. Nothing else
is written on your behalf.

| Path | Committed | What's in it |
|---|---|---|
| `.studious/` | No — gitignored | The per-branch gate ledger (verdicts, episode rounds, the findings ledger), `/next`'s per-feature work files, and the verification evidence a hook captures while a story is armed |
| `docs/studious/` | Yes | `/health` and `/retro` review reports, dated build reports, and the decision journal |

`.studious/` is flow state: local, disposable, and never in the diff — which is why the flow
survives a session ending but not a fresh clone. `studious status` prints what's
recorded for the current branch. `docs/studious/` is the durable record, with one deliberate
exception: `docs/studious/decisions.jsonl` — every `/bet` verdict with its rationale and
what would change the answer — is appended by the gate and committed by you, never
auto-committed by any door.

A third class is written and then deleted: the `/shape` design doc (`docs/design/<slug>.md`)
and `PLAN.md` are gitignored, branch-local, and removed by `/ship` at closeout. They are
working documents for one branch, not project records.

## When something looks wrong

Studious degrades quietly by design — a missing tool or an unregistered skill drops a door
without erroring. `/studious:doctor` is the read-only pass that surfaces it, in five checks:

1. **Tooling** — `git`, `jq`, `gh`, `python3`, `viva`, `gauntlet`. Missing `jq` is the quiet one:
   `studious record` no-ops, so no verdict and no flow position is ever written.
2. **Plugin health** — whether every agent and skill Studious ships actually registered this
   session. Malformed frontmatter on `backlog-priorities` means `/bet` silently runs without
   its ranking lane, without an error.
3. **Context docs** — populated, missing, or still the shipped template.
4. **Flow-state hygiene** — how many active work files have piled up in `.studious/`. Past
   ten, bare `/next` stops resuming one feature and starts asking you to pick from a list.
5. **Retired door names** — greps your CLAUDE.md, README, and `.github/workflows/*.yml` for
   doors that no longer exist, and prints the rewire as a diff.

It fixes nothing, applies nothing, and records no verdict — recommend-only, same as every
review.

## Keeping the project healthy

Separate from the feature flow, two doors run against main, not feature branches.
`/health` inspects what the project *is*: bare `/health` dispatches gauntlet's 7 posture
judges in parallel and compiles a master summary — cross-referenced findings, a
prioritized action plan, and proposed context-doc updates for your approval. `/retro`
looks back at how the cycle went. Trend lives in your issue tracker, not in a report store —
every run reports a baseline. The last four rows below are modes, not lanes: they run only
when you name them.

`/retro` is the retrospective: it reads what Studious recorded while the work happened — the
gate ledger, the decision journal, git history — never the code. It opens
by checking the previous retro's plan item by item, renders the cycle's numbers with
`scripts/retro-stats` (work files by phase, rounds per episode, which lanes blocked,
findings waived or ruled noise, declared-vs-outside scope, time per phase),
says what those rows show went well and badly, proposes changes to the surfaces that govern
the next cycle as diffs — context docs, audit routing, the appetite's measured rung,
story-class heuristics, noise suppressions, idiom rubric lines — and closes with the plan
the next retro opens with. The report lands in `docs/studious/retros/`; a clone with no
ledger gets "no cycle data in this clone", not an error.

| Area | What it checks | Cadence |
|------|----------------|---------|
| `/health codebase` | Structural drift, debt, dead code, dependencies, test health | Weekly or pre-milestone |
| `/health interface` | Cross-surface consistency, design drift, accessibility, interface code | Monthly or post-UI work |
| `/health architecture` | Module boundaries, complexity, evolution readiness | Quarterly |
| `/health product` | PRODUCT.md accuracy, persona drift, scope creep | Monthly |
| `/health security` | Whole-repo vulnerability posture, secrets in history, config posture | Monthly |
| `/health readme` | User-facing docs: stale claims, broken commands, voice drift | After a release |
| `/health prompts` | Trigger coverage, contract alignment, duplication, injection posture | Monthly |
| `/health backlog` | Open issues that are resolved, obsolete, or duplicated | After a review cycle |
| `/health simplify` | Exorcist's séance: standing simplification targets as a register you approve, then `/bet` or `/exorcist:exorcise` (needs exorcist installed) | Quarterly, or before a large refactor |
| `/retro` | The cycle's own ledger: last plan checked, numbers, proposed changes, next plan | After each epic or milestone closes |
| `/retro outcomes` | Shipped merges graded against the fixes and reverts that followed | Quarterly |

Every mode is recommend-only. It writes reports; it never writes code, closes an issue, or
records a verdict.

## Context documents

Everything reads from 3 files in your project root. `/setup` creates them; you maintain them.
Refresh one on its own with `/setup extract-product` or `/setup extract-design`.

| Document | What it holds | Updated by |
|----------|---------------|------------|
| PRODUCT.md | Personas, principles, known problems, "not building" list | You + `/health product` |
| DESIGN.md | Interface conventions per surface — web UI, CLI, TUI, API, or report | You + `/health interface` |
| CLAUDE.md | Technical conventions, workflow reference | You + `/health architecture` |

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
- [gauntlet](https://github.com/jacquardlabs/gauntlet) — a declared dependency, installed
  automatically. `/health` dispatches its seven posture judges and renders their findings
  through gauntlet's published findings contract — separate under the same criterion —
  and `/review`'s changeset lanes are `gauntlet:*` dispatches too. Studious ships the
  consumers and verdict derivation, never the judges (#334).
- [Superpowers](https://github.com/obra/superpowers) — an optional alternative to the
  built-in build loop. Any executor satisfying `reference/worker-contract.md` works.
- GitHub Issues — `/bet` and `/health backlog` read your tracker via the `gh` CLI.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report issues, propose changes, and the
structure conventions for agents, commands, and skills. The door surface itself is data:
[`reference/personas.md`](reference/personas.md) is the charter, and both the CI check and
these docs derive from it.

## License

MIT — see [LICENSE](LICENSE).
