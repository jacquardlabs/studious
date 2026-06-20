# Jaqal

A product development workflow for Claude Code, from [Jacquard Labs](https://github.com/jacquardlabs).

## Why

Claude Code made building cheap. That moved the bottleneck. The hard part is no longer *can we build it*. It's *should we build it, and did we build it right*.

Jaqal adds that judgment back as lightweight gates and reviews woven around the building. It owns the *what* and the *whether*: what to work on, whether a design serves users, whether the implementation delivers, whether the codebase stays healthy. Pair it with [Superpowers](https://github.com/obra/superpowers) for the *how*: brainstorming, planning, TDD, and execution.

## How it works

Jaqal runs on 2 rhythms. A per-feature gate flow that checks each piece of work before and after you build it, and a per-project health loop that reviews the whole on a cadence. Both read from 3 context documents (PRODUCT.md, DESIGN.md, CLAUDE.md) that hold your product's through-lines, so every judgment is grounded in the same context. That's the whole system.

## Install

Via the Jacquard Labs marketplace:

```bash
/plugin marketplace add jacquardlabs/marketplace
/plugin install jaqal@jacquardlabs-marketplace
```

Or directly:

```bash
/plugin marketplace add jacquardlabs/jaqal
/plugin install jaqal@jaqal
```

Then, in any project:

```
/jaqal-init
```

This creates your context documents (PRODUCT.md and DESIGN.md, extracted from the codebase as it actually is), scaffolds the `docs/jaqal/` review directories, and wires the workflow reference into CLAUDE.md so every future session knows the process. Review PRODUCT.md first. The extraction is evidence-based, but product principles and your "not building" list need your voice.

## Building a feature

Jaqal wraps feature development in quality gates. Between them you build, and Jaqal doesn't care how. Each gate exists to catch a specific failure:

- Pick what to build with `/backlog-priorities` (ranks your open GitHub issues by severity/alignment/unblocking potential) or `/gate-should-we-build [idea]` (scores a raw idea against PRODUCT.md and the smallest version worth shipping). Catches building the wrong thing.
- Gate the design with `/gate-design-review`. It walks your design doc as your primary persona would and flags where they'd get confused or frustrated. Catches a bad design before you spend build effort on it.
- Build it with your own workflow. Superpowers gives you plan/execute with TDD and review checkpoints. Jaqal steps back here.
- Audit before merge with `/audit`: 7 auditors in parallel (security, code quality, docs, architecture, UX, frontend, accessibility), each staying in its lane. Frontend auditors skip automatically on branches with no frontend changes.
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
   /audit
         ↓
   /gate-acceptance
         ↓
       merge
```

You don't need every gate every time. For small fixes, `/audit` alone is enough. The gates exist to catch building the wrong thing or shipping a bad experience. Use judgment about when that risk applies.

## Keeping the project healthy

Separate from the feature flow: periodic reviews that assess overall project health. These run against main, not feature branches.

`/deep-review` dispatches all 5 review agents in parallel and compiles a master summary: it cross-references findings across reviews, produces a prioritized action plan, and proposes updates to your context docs for approval. Metrics are captured each run for trend tracking.

Aim it at one area when you don't need the full sweep — each review has its own natural cadence:

| Area | What it checks | Cadence | Run it |
|------|----------------|---------|--------|
| Codebase health | Architecture coherence, tech debt, dependencies, test gaps | Weekly or pre-milestone | `/deep-review codebase` |
| Frontend health | Design drift, accessibility, component quality | Monthly or post-UI work | `/deep-review frontend` |
| Architecture | Module boundaries, complexity, evolution readiness | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | PRODUCT.md accuracy, persona drift, scope creep | Monthly or when it feels off | `/deep-review product` |
| README drift | Stale claims, broken commands, voice | After a release or feature batch | `/deep-review readme` |
| Everything | All 5, cross-referenced into one summary | Monthly | `/deep-review` |

`/backlog-hygiene` scans open GitHub issues against recent commits, PRODUCT.md, and review reports, then flags the ones that are resolved/obsolete/duplicated. Run it after a `/deep-review` to catch what that cycle's fixes resolved. It reports, never modifies.

## Context documents

Everything in Jaqal reads from 3 files in your project root. `/jaqal-init` creates them; you maintain them.

| Document | What it holds | Updated by |
|----------|---------------|------------|
| PRODUCT.md | Personas, principles, known problems, "not building" list | You + `/deep-review product` |
| DESIGN.md | Colors, typography, spacing, component patterns | You + `/deep-review frontend` |
| CLAUDE.md | Technical conventions, review workflow reference | You + `/deep-review architecture` |

Reviews propose updates to these docs. They never apply them. You review and approve. If a doc goes stale, the reviews tell you. That's the point.

## Works well with

- [Superpowers](https://github.com/obra/superpowers): brainstorming, planning, TDD, debugging, and execution. Jaqal gates the what and whether; Superpowers handles the how.
- GitHub Issues: `/backlog-priorities` and `/backlog-hygiene` work with your tracker via the `gh` CLI.

## License

MIT
