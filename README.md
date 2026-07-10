# Studious

A product development workflow for Claude Code, from [Jacquard Labs](https://github.com/jacquardlabs).

## Why

Claude Code made building cheap. That moved the bottleneck. The hard part is no longer *can we build it*. It's *should we build it, and did we build it right*.

Studious adds that judgment back as one discipline entered at the scope of the work: a feature (the gates), a story (`/work-on`), or a whole milestone (`/work-through`). It owns the judgment — what to work on, whether a design serves users, whether the implementation delivers, whether the codebase stays healthy. The building enters through a contract (`reference/worker-contract.md`: story brief in, implementation + evidence out) that any executor can satisfy — you, a dispatched agent, or [Superpowers](https://github.com/obra/superpowers) if you use it.

## How it works

Studious runs on 2 rhythms. A per-feature gate flow that checks each piece of work before and after you build it, and a per-project health loop that reviews the whole on a cadence. Both read from 3 context documents (PRODUCT.md, DESIGN.md, CLAUDE.md) that hold your product's through-lines, so every judgment is grounded in the same context. That's the whole system.

## Quick start

Via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install studious@jacquardlabs-marketplace
```

Or directly:

```bash
/plugin marketplace add jacquardlabs/studious
/plugin install studious@studious
```

Then, in any project:

```
/studious-init
```

This creates your context documents (PRODUCT.md and DESIGN.md, extracted from the codebase as it actually is), scaffolds the `docs/studious/` review directories, and wires the workflow reference into CLAUDE.md so every future session knows the process. Review PRODUCT.md first. The extraction is evidence-based, but product principles and your "not building" list need your voice.

Run `/studious-doctor` any time after — right after install, after a marketplace update, or whenever a gate feels like it ran with less than it should have. It's a read-only check, not a gate: required tooling (git/gh/jq), whether every shipped agent and skill actually registered this session, and whether your context docs are missing or still unedited templates. It fixes nothing, just tells you what to fix. Also fires from natural language — "is my Studious install healthy?".

**From here, the fastest way in is to stop reading and run one command:**

- Building one thing? `/work-on [idea or issue]`. It runs one step of the flow, tells you what's next, and hands back to you at the two steps Studious doesn't own (writing the design, writing the code). Run it again — or just say "next" — when you're ready to keep going.
- Driving a batch? `/work-through [milestone, epic issue, or label]`. It proposes a story plan for your approval, then dispatched agents design, build, and gate each story in parallel, gated exactly like anything else.

Everything past this point is what those two commands are driving underneath — read on for the detail, or to run a piece by hand.

## The gate flow

Studious wraps feature development in quality gates. Between them you build, and Studious doesn't care how. You can drive this yourself one gate at a time, or let a navigator run it for you.

### Let `/work-on` navigate one feature

`/work-on [idea or issue]` walks a feature through the gate sequence below, one piece per invocation. Each invocation runs exactly one step — a gate, or a handoff at the two steps Studious doesn't own (design doc, build) — then stops and tells you what the next piece is. There is no auto-advance. When you're ready, `/work-on` with no argument (or just "next", or "do the next piece") runs it; you never have to remember which gate comes after which. Position is tracked per feature in local, gitignored `.studious/` state, so the flow survives across sessions and picks up where the feature actually stands — including gates you ran by hand.

### Let `/work-through` drive a whole milestone

`/work-through [milestone, epic issue, or label]` scales the flow up a level. The first run reads the milestone's issues (read-only) and proposes a story plan — dependency order, acceptance criteria per story, which gates each story needs, an epic-level pre-mortem — then stops for your approval; nothing runs before it. Every run after that drives: agents design, build, and gate stories in parallel worktrees (3 at once by default), stories that pass their gates merge into an `epic/<name>` integration branch, and fix-it verdicts get at most 2 repair cycles with a fresh auditor each time. Judgment verdicts — RETHINK, NEEDS DISCUSSION, HOLD — never retry: that story parks for you while independent stories keep moving. When everything lands, the whole epic diff gets a final audit plus an acceptance check against the epic's goal, and the branch is yours (`gh pr create` — same ledger, same PR-time hook). Any parked story is a normal `/work-on` feature, so you can always take one over by hand. Fair warning: an epic run spends tokens like the 5–10 supervised flows it replaces.

The driver has two execution modes with identical semantics, interchangeable mid-epic: the primary mode runs the scheduling as a deterministic Workflow script (`workflows/epic-driver.js` — DAG order, concurrency, retry caps, and merge order in code, so bookkeeping never burns model context and cannot be improvised), and a prompt-driven fallback covers environments without the Workflow tool. Judgment — decompositions, gate verdicts, fixes, park explanations — lives in dispatched agents in both modes.

### Run a gate directly

Each gate exists to catch a specific failure. Reach for one on its own when you don't need the full navigator — a small fix, or picking up a feature mid-flow by hand:

- Pick what to build with `/backlog-priorities` (ranks your open GitHub issues by severity/alignment/unblocking potential) or `/gate-should-we-build [idea]` (scores a raw idea against PRODUCT.md and the smallest version worth shipping). Catches building the wrong thing.
- Gate the design with `/gate-design-review`. It walks your design doc as your primary persona would and flags where they'd get confused or frustrated. Catches a bad design before you spend build effort on it. On a passing verdict, it also writes a pre-mortem register (`docs/studious/premortems/<slug>.md`) — failure modes predicted at design time, checked back against the finished changeset at the end of the flow.
- Build it with your own workflow — by hand or with any executor (Superpowers works well here). Studious steps back in the supervised flow; in `/work-through` epics, dispatched workers build to `reference/worker-contract.md` and are gated like anyone else.
- Audit before merge with `/gate-audit`. Security, code quality, docs, architecture, and test adequacy always run; UX, frontend, and an accessibility pass (via the `web-design-guidelines` skill, or a vendored fallback when it isn't installed) join in on projects with a web surface; infrastructure joins in when the changeset touches IaC, container, or CI-pipeline files; and if the design-review gate recorded a pre-mortem register for this branch, a dedicated auditor checks each predicted failure mode — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 10 auditors, each staying in its lane.
- Gate acceptance with `/gate-acceptance`. Product review, not code review: does the implementation actually deliver the experience? It walks every user-facing change, checks error states for human-friendly messaging, regression-tests the critical journeys in PRODUCT.md, and — same register, other half — verifies the pre-mortem's product-lane items against what shipped.

```
/backlog-priorities  or  /gate-should-we-build [idea]
         ↓
   design doc
         ↓
   /gate-design-review  →  writes pre-mortem register
         ↓
   implement
         ↓
   /gate-audit  →  verifies technical-lane register items
         ↓
   /gate-acceptance  →  verifies product-lane register items
         ↓
   gh pr create
         ↓
       merge
```

When you run `gh pr create`, a PR-time hook reads the gate verdicts recorded to a local `.studious/` ledger (which Studious adds to your `.gitignore` on first run) and gives a specific reminder — naming gates that never ran, ran on an older commit, or didn't pass — while staying non-blocking.

You don't need every gate every time. For small fixes, `/gate-audit` alone is enough. The gates exist to catch building the wrong thing or shipping a bad experience. Use judgment about when that risk applies.

The three product gates also fire from natural language, not just the slash command — asking "should we build this?", "review this design before I build it", or "does this actually deliver?" routes to the matching gate. So does flow continuation — "do the next piece" resumes `/work-on`. Triggers are deliberately conservative, so you'll still reach for the commands directly most of the time.

## CI mode (optional)

`.github/workflows/gate-audit-pr.yml` runs `/gate-audit` non-interactively against a PR and posts the report as a PR comment — the same auditor fan-out you'd get locally (up to 10, depending on the project's web surface, whether the changeset touches infrastructure files, and whether a pre-mortem register exists), without anyone having to remember to run it. It ships **dormant** (manual `workflow_dispatch` trigger only): pick a PR, run the workflow from the Actions tab with that PR's number as input, and it audits that PR and comments on it. It does not fire automatically on every PR yet.

To set it up:

1. Add `ANTHROPIC_API_KEY` as a repository secret (Settings → Secrets and variables → Actions). Without it, the job fails at the "Run gate-audit headlessly" step.
2. Test it manually first: `workflow_dispatch` it against a real, non-draft, same-repo PR and read the comment it posts before trusting it further.
3. To make it run automatically on every PR instead of by hand, change the workflow's `on:` block from `workflow_dispatch` (with the `pr_number` input) to `pull_request: types: [opened, synchronize, reopened, ready_for_review]`, and swap every `inputs.pr_number` reference for `github.event.pull_request.number` (and the head/base SHA resolution step can be dropped in favor of `github.event.pull_request.head.sha` / `.base.sha` directly).

It refuses draft PRs and fork PRs (no repository secrets are available to fork-triggered runs, and this keeps the agent's Bash access scoped to contributors who already have write access), and skips diffs over 40 changed files to keep the fan-out's cost bounded — see the workflow file's own comments for the full reasoning.

## Keeping the project healthy

Separate from the feature flow: periodic reviews that assess overall project health. These run against main, not feature branches.

`/deep-review` dispatches all 6 review agents in parallel and compiles a master summary: it cross-references findings across reviews, produces a prioritized action plan, and proposes updates to your context docs for approval. Metrics are captured each run for trend tracking.

Aim it at one area when you don't need the full sweep — each review has its own natural cadence:

| Area | What it checks | Cadence | Run it |
|------|----------------|---------|--------|
| Codebase health | Architecture coherence, tech debt, dependencies, test gaps | Weekly or pre-milestone | `/deep-review codebase` |
| Interface health | Cross-surface consistency, design drift, accessibility (web), interface code quality | Monthly or post-UI work | `/deep-review interface` |
| Architecture | Module boundaries, complexity, evolution readiness | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | PRODUCT.md accuracy, persona drift, scope creep | Monthly or when it feels off | `/deep-review product` |
| Security health | Whole-repo vulnerability posture, secrets in git history, security-config posture | Monthly | `/deep-review security` |
| README drift | Stale claims, broken commands, voice | After a release or feature batch | `/deep-review readme` |
| Everything | All 6, cross-referenced into one summary | Monthly | `/deep-review` |

`/backlog-hygiene` scans open GitHub issues against recent commits, PRODUCT.md, and review reports, then flags the ones that are resolved/obsolete/duplicated. Run it after a `/deep-review` to catch what that cycle's fixes resolved. It reports, never modifies.

## Context documents

Everything in Studious reads from 3 files in your project root. `/studious-init` creates them; you maintain them.

| Document | What it holds | Updated by |
|----------|---------------|------------|
| PRODUCT.md | Personas, principles, known problems, "not building" list | You + `/deep-review product` |
| DESIGN.md | Your interface conventions — the user-facing surface(s), whether web UI, CLI, TUI, API, or report | You + `/deep-review interface` |
| CLAUDE.md | Technical conventions, review workflow reference | You + `/deep-review architecture` |

Reviews propose updates to these docs. They never apply them. You review and approve. If a doc goes stale, the reviews tell you. That's the point.

## Works well with

- [Superpowers](https://github.com/obra/superpowers): an optional executor for the build step — brainstorming, planning, TDD, debugging. Studious owns the gates and the worker contract; any executor that satisfies the contract works, Superpowers included.
- GitHub Issues: `/backlog-priorities` and `/backlog-hygiene` work with your tracker via the `gh` CLI.

## License

MIT
