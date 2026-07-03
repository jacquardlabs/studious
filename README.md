# Studious

A product development workflow for Claude Code, from [Jacquard Labs](https://github.com/jacquardlabs).

## Why

Claude Code made building cheap. That moved the bottleneck. The hard part is no longer *can we build it*. It's *should we build it, and did we build it right*.

Studious adds that judgment back as lightweight gates and reviews woven around the building. It owns the *what* and the *whether*: what to work on, whether a design serves users, whether the implementation delivers, whether the codebase stays healthy. Pair it with [Superpowers](https://github.com/obra/superpowers) for the *how*: brainstorming, planning, TDD, and execution.

## How it works

Studious runs on 2 rhythms. A per-feature gate flow that checks each piece of work before and after you build it, and a per-project health loop that reviews the whole on a cadence. Both read from 3 context documents (PRODUCT.md, DESIGN.md, CLAUDE.md) that hold your product's through-lines, so every judgment is grounded in the same context. That's the whole system.

## Install

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

## Building a feature

Studious wraps feature development in quality gates. Between them you build, and Studious doesn't care how. Each gate exists to catch a specific failure:

- Pick what to build with `/backlog-priorities` (ranks your open GitHub issues by severity/alignment/unblocking potential) or `/gate-should-we-build [idea]` (scores a raw idea against PRODUCT.md and the smallest version worth shipping). Catches building the wrong thing.
- Gate the design with `/gate-design-review`. It walks your design doc as your primary persona would and flags where they'd get confused or frustrated. Catches a bad design before you spend build effort on it.
- Build it with your own workflow. Superpowers gives you plan/execute with TDD and review checkpoints. Studious steps back here.
- Audit before merge with `/gate-audit`: 6 auditors in parallel (security, code quality, docs, architecture, UX, frontend), each staying in its lane, plus an accessibility pass via the `web-design-guidelines` skill (Web Interface Guidelines) when it's installed. The 3 web auditors skip automatically on projects with no web surface and on branches with no frontend changes.
- Gate acceptance with `/gate-acceptance`. Product review, not code review: does the implementation actually deliver the experience? It walks every user-facing change, checks error states for human-friendly messaging, and regression-tests the critical journeys in PRODUCT.md.

```
/backlog-priorities  or  /gate-should-we-build [idea]
         ↓
   design doc
         ↓
   /gate-design-review
         ↓
   implement
         ↓
   /gate-audit
         ↓
   /gate-acceptance
         ↓
   gh pr create
         ↓
       merge
```

When you run `gh pr create`, a PR-time hook reads the gate verdicts recorded to a local `.studious/` ledger (which Studious adds to your `.gitignore` on first run) and gives a specific reminder — naming gates that never ran, ran on an older commit, or didn't pass — while staying non-blocking.

You don't need every gate every time. For small fixes, `/gate-audit` alone is enough. The gates exist to catch building the wrong thing or shipping a bad experience. Use judgment about when that risk applies.

The three product gates also fire from natural language, not just the slash command — asking "should we build this?", "review this design before I build it", or "does this actually deliver?" routes to the matching gate. Triggers are deliberately conservative, so you'll still reach for the commands directly most of the time.

## CI mode (optional)

`.github/workflows/gate-audit-pr.yml` runs `/gate-audit` non-interactively against a PR and posts the report as a PR comment — the same 6-7 auditor fan-out you'd get locally, without anyone having to remember to run it. It ships **dormant** (manual `workflow_dispatch` trigger only): pick a PR, run the workflow from the Actions tab with that PR's number as input, and it audits that PR and comments on it. It does not fire automatically on every PR yet.

To set it up:

1. Add `ANTHROPIC_API_KEY` as a repository secret (Settings → Secrets and variables → Actions). Without it, the job fails at the "Run gate-audit headlessly" step.
2. Test it manually first: `workflow_dispatch` it against a real, non-draft, same-repo PR and read the comment it posts before trusting it further.
3. To make it run automatically on every PR instead of by hand, change the workflow's `on:` block from `workflow_dispatch` (with the `pr_number` input) to `pull_request: types: [opened, synchronize, reopened, ready_for_review]`, and swap every `inputs.pr_number` reference for `github.event.pull_request.number` (and the head/base SHA resolution step can be dropped in favor of `github.event.pull_request.head.sha` / `.base.sha` directly).

It refuses draft PRs and fork PRs (no repository secrets are available to fork-triggered runs, and this keeps the agent's Bash access scoped to contributors who already have write access), and skips diffs over 40 changed files to keep the fan-out's cost bounded — see the workflow file's own comments for the full reasoning.

## Keeping the project healthy

Separate from the feature flow: periodic reviews that assess overall project health. These run against main, not feature branches.

`/deep-review` dispatches all 5 review agents in parallel and compiles a master summary: it cross-references findings across reviews, produces a prioritized action plan, and proposes updates to your context docs for approval. Metrics are captured each run for trend tracking.

Aim it at one area when you don't need the full sweep — each review has its own natural cadence:

| Area | What it checks | Cadence | Run it |
|------|----------------|---------|--------|
| Codebase health | Architecture coherence, tech debt, dependencies, test gaps | Weekly or pre-milestone | `/deep-review codebase` |
| Interface health | Cross-surface consistency, design drift, accessibility (web), interface code quality | Monthly or post-UI work | `/deep-review interface` |
| Architecture | Module boundaries, complexity, evolution readiness | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | PRODUCT.md accuracy, persona drift, scope creep | Monthly or when it feels off | `/deep-review product` |
| README drift | Stale claims, broken commands, voice | After a release or feature batch | `/deep-review readme` |
| Everything | All 5, cross-referenced into one summary | Monthly | `/deep-review` |

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

- [Superpowers](https://github.com/obra/superpowers): brainstorming, planning, TDD, debugging, and execution. Studious gates the what and whether; Superpowers handles the how.
- GitHub Issues: `/backlog-priorities` and `/backlog-hygiene` work with your tracker via the `gh` CLI.

## License

MIT
