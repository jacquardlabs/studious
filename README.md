# Studious

[![CI](https://github.com/jacquardlabs/studious/actions/workflows/ci.yml/badge.svg)](https://github.com/jacquardlabs/studious/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jacquardlabs/studious)](https://github.com/jacquardlabs/studious/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A product development workflow for Claude Code, from [Jacquard Labs](https://github.com/jacquardlabs).

## Why

Claude Code made building cheap. That moved the bottleneck. The hard part is no longer *can we build it*. It's *should we build it, and did we build it right*.

Studious adds that judgment back as one discipline entered at the scope of the work: a feature (the gates), a story (`/next`), or a whole milestone (`/next`). It owns the judgment: what to work on, whether a design serves users, whether the implementation delivers, whether the codebase stays healthy. The building enters through a contract (`reference/worker-contract.md`: story brief in, implementation and evidence out). A build loop that satisfies it ships in the box (`/shape` → `/build` → `/build` → `/ship`), and so does any other executor you prefer — you by hand, a dispatched agent, or [Superpowers](https://github.com/obra/superpowers). No gate knows or cares which built the branch; CI enforces that.

## How it works

Studious runs on 2 rhythms. A per-feature gate flow that checks each piece of work before and after you build it, and a per-project health loop that reviews the whole on a cadence. Both read from 3 context documents (PRODUCT.md, DESIGN.md, CLAUDE.md) that hold your product's through-lines, so every judgment is grounded in the same context. Between the gates you build — with the loop Studious ships, or with anything else. That's the whole system.

## Quick start

Via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install studious@jacquardlabs-marketplace
```

That also installs [viva](https://github.com/jacquardlabs/viva), a declared dependency: `/shape` and `/build` drive it for their human sign-off rounds, and Claude Code resolves it from the same marketplace automatically.

Then, in any project:

```
/setup
```

This creates your context documents (PRODUCT.md and DESIGN.md, extracted from the codebase as it actually is), scaffolds the `docs/studious/` review directories, and wires the workflow reference into CLAUDE.md so every future session knows the process. Review PRODUCT.md first. The extraction is evidence-based, but product principles and your "not building" list need your voice.

Run `/doctor` any time after: right after install, after a marketplace update, or whenever a gate feels like it ran with less than it should have. It's a read-only check, not a gate: required tooling (git/gh/jq), whether every shipped agent and skill actually registered this session, and whether your context docs are missing or still unedited templates. It fixes nothing, just tells you what to fix. It also fires from natural language — "is my Studious install healthy?"

**From here, the fastest way in is to stop reading and run one command:**

- Start here: `/next [milestone, epic issue, or label]`. It proposes a story plan — including which stories it will drive unattended and which it will hand back to you — interviews you once for the whole epic, then dispatched agents design, build, and gate the unattended ones in parallel. Same gates as anywhere else. It's the front door even for one story: a plan of one is cheap, and the classification is the part you want.
- Taking one thing over by hand? `/next [idea or issue]`. It runs one step of the flow, tells you what's next, and hands back to you at the two steps Studious doesn't own (writing the design, writing the code). Run it again, or just say "next," when you're ready to keep going. It's also where `/next` sends the work it won't drive unattended.

Everything past this point is what those two commands are driving underneath — read on for the detail, or to run a piece by hand.

## The gate flow

Studious wraps feature development in quality gates. Between them you build, and Studious doesn't care how. You can drive this yourself one gate at a time, or let a navigator run it for you.

### Let `/next` drive the work

`/next [milestone, epic issue, or label]` is the front door. The first run reads the milestone's issues (read-only) and proposes a story plan: dependency order, acceptance criteria per story, which gates each story needs, an epic-level pre-mortem. It also interviews you once for the whole epic — 10–12 questions, capped, covering only the product forks a worker can't decide alone — because every phase after this runs in a subagent with no human in its loop. Then it stops for your approval; nothing runs before it.

**You approve a price, not just a scope.** The same stop shows what the plan will cost to run — a token estimate computed per story from its gate profile, shown with its parts and its fix-cycle range — and asks you to approve two ceilings: a token appetite, and a cap on how many stories may be awaiting you at once. The script driver holds both at runtime; the prompt fallback holds the episode cap and reports, rather than enforces, the token one. It also names the canary: the first invocation dispatches exactly one dependency-free story and releases the rest only once it lands, so a bad plan costs one story to discover rather than a full-width run. All of it is yours to move before you approve.

**The plan says which stories it will drive and which it hands back.** Each story is classed at plan time, from the files it says it will touch and the shape of its source issue. A story whose surface is code with executable verification, backed by an issue that already carries acceptance criteria with citations, is `epic-default`: the driver runs its whole profile unattended. A story whose file set is majority prompt-prose, or that starts as a raw idea with no acceptance criteria, or that is the first of its kind in this epic, is `story-supervised`: it stays in the plan but comes back to you as a `/next` handoff in the run's "Needs you" queue. You see the class and the reason next to every story before you approve, and you can overturn either.

**Know what you're trading.** For the stories it drives, you approve the story plan and answer the interview, and the next thing you see is the epic PR. You don't approve those design docs: `/review` reviews every one of them, but that's an agent reviewing, not you signing off. A subagent can't open a browser, and the driver is barred from routing to `/shape` by the same rule that keeps gates executor-agnostic. That trade is why the classification exists — the work where a gate can't verify the thing you'd have checked never takes it, and comes to you instead.

Every run after that drives execution: agents design, build, and gate stories in parallel worktrees (5 at once by default). Stories that pass their gates merge into an `epic/<name>` integration branch, and fix-it verdicts get at most 2 repair cycles with a fresh auditor each time. Judgment verdicts (RETHINK, NEEDS DISCUSSION, HOLD) never retry: that story parks for you while independent stories keep moving.

When everything lands, the whole epic diff gets a final audit plus an acceptance check against the epic's goal, and the branch is yours (`gh pr create`, same ledger, same PR-time hook). Any parked story — supervised at plan time, or parked mid-run on a judgment verdict — is a normal `/next` feature, so you can always take one over by hand. A run also reports a third outcome, `Held`: a story a ceiling you approved stopped before it was ever dispatched (the token appetite ran out, the open-episode cap was full, or the canary didn't land). A held story earned no verdict and asks nothing of you — clear the queue or re-run with headroom and it goes. Fair warning: an epic run spends tokens like the 5–10 supervised flows it replaces.

The driver has two execution modes with identical semantics, interchangeable mid-epic. The primary mode runs the scheduling as a deterministic Workflow script (`workflows/epic-driver.js`, handling DAG order, concurrency, retry caps, and merge order in code, so bookkeeping never burns model context and cannot be improvised). A prompt-driven fallback covers environments without the Workflow tool. Judgment (decompositions, gate verdicts, fixes, park explanations) lives in dispatched agents in both modes.

### Let `/next` take one feature over

`/next [idea or issue]` walks a single feature through the gate sequence below, one piece per invocation. Reach for it two ways: to take over a story `/next` classed `story-supervised` or parked mid-run, or to drive something by hand from the start. Each invocation runs exactly one step: a gate, or a handoff at the two steps Studious doesn't own (design doc, build). Then it stops and tells you what the next piece is. There is no auto-advance. When you're ready, `/next` with no argument (or just "next", or "do the next piece") runs it; you never have to remember which gate comes after which. Position is tracked per feature in local, gitignored `.studious/` state, so the flow survives across sessions and picks up where the feature actually stands, including gates you ran by hand. A design doc here gets your sign-off as well as the gate — that is the whole difference between the two, and the reason the plan piece routes work it can't verify mechanically to this command.

### Run a gate directly

Each gate exists to catch a specific failure. Reach for one on its own when you don't need the full navigator — a small fix, or picking up a feature mid-flow by hand:

- Pick what to build with `/bet` (ranks your open GitHub issues by severity/alignment/unblocking potential) or `/bet [idea]` (scores a raw idea against PRODUCT.md and the smallest version worth shipping). Catches building the wrong thing.
- Gate the design with `/review`. It walks your design doc as your primary persona would and flags where they'd get confused or frustrated. Catches a bad design before you spend build effort on it. On a passing verdict, it also writes a pre-mortem register (`docs/studious/premortems/<slug>.md`) — failure modes predicted at design time, checked back against the finished changeset at the end of the flow.
- Build it with `/build` and `/build` (see [The build loop](#the-build-loop)), or with any other executor — by hand, or Superpowers. The gates step back in the supervised flow; in `/next` epics, dispatched workers build to `reference/worker-contract.md` and are gated like anyone else.
- Audit before merge with `/review`. Security, code quality, docs, architecture, and test adequacy always run; UX, frontend, and an accessibility pass (via the `web-design-guidelines` skill, or a vendored fallback when it isn't installed) join in on projects with a web surface; infrastructure joins in when the changeset touches IaC, container, or CI-pipeline files; operability joins in when the changeset touches runtime code (request handlers, queue consumers, daemons, outbound calls); a dependency check joins in when the changeset touches dependency manifests or lockfiles (new or updated packages, known vulnerabilities, license compatibility, maintenance signal, lockfile-manifest drift); a prompt check joins in when the changeset touches prompt files — agent/command/skill definitions, model-facing instruction docs, prompt templates (trigger reliability, instruction conflicts, orchestrator-subagent contract drift, duplication, injection safety, runtime identity, token economy); and if the design-review gate recorded a pre-mortem register for this branch, a dedicated auditor checks each predicted failure mode — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 13 auditors, each staying in its lane.
- Gate acceptance with `/review --delivery`. Product review, not code review: does the implementation actually deliver the experience? It walks every user-facing change, checks error states for human-friendly messaging, regression-tests the critical journeys in PRODUCT.md, and verifies the pre-mortem's product-lane items against what shipped (same register, other half).

```
/bet  or  /bet [idea]
         ↓
   design doc
         ↓
   /review  →  writes pre-mortem register
         ↓
   implement
         ↓
   /review  →  verifies technical-lane register items
         ↓
   /review --delivery  →  verifies product-lane register items
         ↓
   gh pr create
         ↓
       merge
```

When you run `gh pr create`, a PR-time hook reads the gate verdicts recorded to a local `.studious/` ledger (which Studious adds to your `.gitignore` on first run) and gives a specific reminder (naming gates that never ran, ran on an older commit, or didn't pass) while staying non-blocking.

You don't need every gate every time. For small fixes, `/review` alone is enough. The gates exist to catch building the wrong thing or shipping a bad experience. Use judgment about when that risk applies.

The three product gates also fire from natural language, not just the slash command: asking "should we build this?", "review this design before I build it", or "does this actually deliver?" routes to the matching gate. So does flow continuation — "do the next piece" resumes `/next`. Triggers are deliberately conservative, so you'll still reach for the commands directly most of the time.

## The build loop

Two steps in the gate flow above — the `design doc` and `implement` boxes — are what the gates judge but don't perform. Studious ships a route through both. Use it, or don't; the gates can't tell.

- `/shape` inventories your context docs and the code the change touches, runs one batch interview of 5–9 questions (forks as 2–3 options, one recommended), drafts `design-<slug>.md` section by section, and holds every section at a viva sign-off round in the browser until you approve it. Reports `DESIGNED`, `NEEDS RESEARCH`, or `REVISED`.
- `/build` turns that doc into a `PLAN.md`: a dependency spine, 3–8 calibrated tasks, and a checkpoint block per task tagged `LOW`, `REPLAN-RISK`, or `ESCALATE-RISK`. `scripts/plan-lint` has to exit 0, then viva reviews one card per task. Reports `PLAN READY`, `DESIGN GAP`, or `TOO BIG`.
- `/build` works the plan one task at a time in a fresh, isolated executor, verifies each by running the task's own commands, and captures the output as evidence. Status flips are written by scripts, never by the model, and load-bearing tasks get a fresh inspector that judges exactly test self-dealing, contract match, and technicality gaming. Reports `BUILT`, `PAUSED`, or `ESCALATED`, and never auto-continues past a pause.
- `/ship` closes out a `BUILT` branch: an evidence table mapping each done-means item to how it was verified, follow-ups filed only on per-item confirmation, proposed (never applied) patches to PRODUCT.md/DESIGN.md/CLAUDE.md, and a dated build report. Reports `MERGE`, `PR`, `KEEP`, or `DISCARD`.
- `/next` reads the repo and tells you where you are and the single next action, with rough cost. It does no work itself and dispatches nothing without your say-so.

`/shape` and `/build` require [viva](https://github.com/jacquardlabs/viva) for their sign-off rounds — a declared dependency, so it installs with Studious.

**`/next` or `/next`?** They navigate the same flow and share the same state file, so a feature tracked by one is visible to the other — you can switch mid-feature and neither loses the thread. Pick by what you want done, not by where you are:

| | `/next` | `/next` |
|---|---|---|
| Does | Runs the next gate and records its verdict | Reads, then recommends one action |
| Hands off by | Stopping and telling you what's next | Dispatching a build skill, only on your explicit yes |
| Writes | The work file | Nothing at all |
| Reach for it when | You want to advance the feature | You're re-entering cold, or a `PAUSED`/`ESCALATED` build left you unsure what to do |

**No gate requires any of this.** `scripts/check_gate_independence.py` fails CI if a gate command, agent, driver, hook, or the ledger so much as invokes a build skill or reads a build artifact. What a gate may rely on is `reference/evidence-format.md`, which any executor can satisfy.

## CI mode (optional)

`.github/workflows/gate-audit-pr.yml` runs `/review` non-interactively against a PR and posts the report as a PR comment — the same auditor fan-out you'd get locally (up to 13, depending on the project's web surface, whether the changeset touches infrastructure files, runtime code, dependency manifests, or prompt files, and whether a pre-mortem register exists), without anyone having to remember to run it. It ships **dormant** (manual `workflow_dispatch` trigger only): pick a PR, run the workflow from the Actions tab with that PR's number as input, and it audits that PR and comments on it. It does not fire automatically on every PR yet.

To set it up:

1. Add `ANTHROPIC_API_KEY` as a repository secret (Settings → Secrets and variables → Actions). Without it, the job fails at the "Run gate-audit headlessly" step.
2. Test it manually first: `workflow_dispatch` it against a real, non-draft, same-repo PR and read the comment it posts before trusting it further.
3. To make it run automatically on every PR instead of by hand, change the workflow's `on:` block from `workflow_dispatch` (with the `pr_number` input) to `pull_request: types: [opened, synchronize, reopened, ready_for_review]`, and swap every `inputs.pr_number` reference for `github.event.pull_request.number` (and the head/base SHA resolution step can be dropped in favor of `github.event.pull_request.head.sha` / `.base.sha` directly).

It refuses draft PRs and fork PRs (no repository secrets are available to fork-triggered runs, and this keeps the agent's Bash access scoped to contributors who already have write access), and skips diffs over 40 changed files to keep the fan-out's cost bounded — see the workflow file's own comments for the full reasoning.

## Keeping the project healthy

Separate from the feature flow: periodic reviews that assess overall project health. These run against main, not feature branches.

`/retro` dispatches all 7 review agents in parallel and compiles a master summary: it cross-references findings across reviews, produces a prioritized action plan, and proposes updates to your context docs for approval. Metrics are captured each run for trend tracking.

Aim it at one area when you don't need the full sweep — each review has its own natural cadence:

| Area | What it checks | Cadence | Run it |
|------|----------------|---------|--------|
| Codebase health | Architecture coherence, tech debt, dependencies, test gaps | Weekly or pre-milestone | `/retro codebase` |
| Interface health | Cross-surface consistency, design drift, accessibility (web), interface code quality | Monthly or post-UI work | `/retro interface` |
| Architecture | Module boundaries, complexity, evolution readiness | Quarterly or pre-major-feature | `/retro architecture` |
| Product health | PRODUCT.md accuracy, persona drift, scope creep | Monthly or when it feels off | `/retro product` |
| Security health | Whole-repo vulnerability posture, secrets in git history, security-config posture | Monthly | `/retro security` |
| README drift | Stale claims, broken commands, voice | After a release or feature batch | `/retro readme` |
| Prompt health | Trigger coverage, instruction consistency, contract alignment, duplication, injection posture, token economy | Monthly (repos with a prompt surface; auto-skips otherwise) | `/retro prompts` |
| Everything | All 7, cross-referenced into one summary | Monthly | `/retro` |

`/retro` scans open GitHub issues against recent commits, PRODUCT.md, and review reports, then flags the ones that are resolved/obsolete/duplicated. Run it after a `/retro` to catch what that cycle's fixes resolved. It reports, never modifies.

## Context documents

Everything in Studious reads from 3 files in your project root. `/setup` creates them; you maintain them. To rebuild one on its own after drift, `/setup` and `/setup` re-run the same evidence-based extraction against the current codebase.

| Document | What it holds | Updated by |
|----------|---------------|------------|
| PRODUCT.md | Personas, principles, known problems, "not building" list | You + `/retro product` |
| DESIGN.md | Your interface conventions — the user-facing surface(s), whether web UI, CLI, TUI, API, or report | You + `/retro interface` |
| CLAUDE.md | Technical conventions, review workflow reference | You + `/retro architecture` |

Reviews propose updates to these docs. They never apply them. You review and approve. If a doc goes stale, the reviews tell you. That's the point.

## Commands

Every command Studious ships, for quick reference:

| Command | What it does |
|---------|---------------|
| `/setup` | Creates PRODUCT.md and DESIGN.md, scaffolds review directories, and configures CLAUDE.md. |
| `/doctor` | Checks tooling, plugin registration, and context-doc health for silent-degradation risks. |
| `/next [idea or issue]` | Navigates the feature flow one piece at a time. |
| `/next [milestone, epic issue, or label]` | Drives a whole milestone through the gate flow with dispatched agents. |
| `/bet` | Curates a ranked shortlist from open GitHub issues based on your current intent. |
| `/retro` | Identifies open GitHub issues that should be closed. Recommend-only. |
| `/bet [idea]` | Evaluates whether a feature idea is worth building before any engineering begins. |
| `/review` | Product review of a design doc before implementation begins. |
| `/review` | Runs the audit suite — security, code quality, docs, architecture, and tests, scoped to the changeset. |
| `/review --delivery` | Product acceptance review after implementation, before merge. |
| `/shape` | Interviews you, drafts a design doc, and holds it at a viva sign-off round per section. |
| `/build` | Turns a design doc into a lint-clean `PLAN.md` of 3–8 tasks with checkpoint blocks. |
| `/build` | Works the plan one task at a time in a fresh executor, script-verified, evidence captured. |
| `/ship` | Closes out a `BUILT` branch: evidence table, follow-ups, build report, merge decision. |
| `/next` | Reads the repo and names the single next action in the build loop. |
| `/retro [area]` | Runs the periodic review suite: one area, or all 7 with a compiled summary. |
| `/retro [weeks]` | Grades shipped merges against the fixes and reverts that followed them. Recommend-only. |
| `/setup` | Extracts the interface design system from the codebase into DESIGN.md. |
| `/setup` | Extracts product context from the codebase into PRODUCT.md. |

## Works well with

- [viva](https://github.com/jacquardlabs/viva): a declared dependency, installed automatically. `/shape` and `/build` drive it for their human sign-off rounds — section-by-section review in the browser, through viva's published headless contract. It stays a separate repo because that contract is versioned and tested, not a format convention.
- [Superpowers](https://github.com/obra/superpowers): an optional alternative to the built-in build loop. Studious owns the gates and the worker contract; any executor that satisfies the contract works, and no gate requires the built-in one — CI enforces that.
- GitHub Issues: `/bet` and `/retro` work with your tracker via the `gh` CLI.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report issues, propose changes, and the structure conventions for agents, commands, and skills.

## License

MIT — see [LICENSE](LICENSE).
