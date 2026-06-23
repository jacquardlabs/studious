# Product context

## Why this product exists

Based on the README and the `.claude-plugin/plugin.json` description, Studious is a
product-judgment workflow for Claude Code. Its thesis, stated directly in the README:

> "Claude Code made building cheap. That moved the bottleneck. The hard part is no
> longer *can we build it*. It's *should we build it, and did we build it right*."

Studious adds that judgment back as lightweight gates and reviews woven around the
building. It owns the *what* and the *whether* — what to work on, whether a design
serves users, whether the implementation delivers, whether the codebase stays
healthy. It deliberately does **not** own the *how* (see "What we're NOT building"),
deferring brainstorming, planning, TDD, and execution to a companion product
(Superpowers).

Origin: the project was previously named Jaqal and renamed to Studious at v2.0.0
(commit `2e1809c`, PR #35). Authored by Jacquard Labs; MIT-licensed; distributed as a
Claude Code plugin via the Jacquard Labs marketplace.

## Who uses it

The product is a Claude Code plugin (markdown commands, agents, skills, and one
hook). Its users are therefore Claude Code users. The workflow's assumptions —
present in the commands and agents — reveal the intended user more precisely than the
README does.

### Primary persona

**A developer (solo or small team) building features with Claude Code who wants
product judgment and quality gates woven into the build, without heavy process.**

Evidence:
- The feature flow assumes feature-branch development with PRs: gates run "before and
  after you build it"; periodic reviews "run against main, not feature branches"; a
  `PreToolUse` hook fires on `gh pr create` (`hooks/gate-reminder.sh`).
- The backlog commands operate on GitHub Issues via the `gh` CLI
  (`/backlog-priorities`, `/backlog-hygiene`), so the user works in a GitHub repo.
- The whole system reads three context docs (PRODUCT.md, DESIGN.md, CLAUDE.md) the
  user maintains — a user who values durable, shared context over per-prompt
  re-explanation.
- The README frames the pairing explicitly: "Studious gates the what and whether;
  Superpowers handles the how" — the user is someone who already builds fast with AI
  and feels the judgment bottleneck, not the building bottleneck.

### Secondary persona

**The maintainer dogfooding Studious on Studious.** The project is itself developed
under its own workflow (`docs/studious/` review directories, gate verdicts recorded
directly on roadmap issues, a v1.5 release described as "remediate the behavioral
audit"). This persona is why gaps like the once-empty PRODUCT.md and the formerly
web-only DESIGN.md (issue #25, closed by this change) surfaced as real, tracked
problems rather than hypotheticals.

<!-- FILL IN: Is the small-team/team-lead angle a real target, or is the primary
     audience individual builders? The code supports both; intent is yours to set. -->

## Product principles

These are drawn from the README and the consistent behavior of the commands/agents.
They read as the de facto principles driving the product; confirm and refine them —
this section is your voice, not the extractor's.

- **Own the *what* and the *whether*, not the *how*** — Studious gates judgment
  (should we build it, did we build it right) and stays out of implementation
  mechanics, deferring those to Superpowers. This boundary is the product's spine.
- **Propose, don't apply** — reviews surface findings and propose updates to context
  docs, but never write them. "They never apply them. You review and approve." The
  human stays the decision-maker.
- **Grounded in shared context** — every gate and review reads from the same three
  context docs, so judgments are consistent rather than per-prompt improvisation.
- **Evidence over invention** — extraction documents "what IS, including
  inconsistencies," and never idealizes. The audit idiom rubrics defer to the
  project's own CLAUDE.md conventions over built-in defaults.
- **Lightweight and optional** — "You don't need every gate every time." Gates are a
  toolkit applied by judgment, and natural-language triggers are "deliberately
  conservative" to avoid firing unbidden.
- **Stay in your lane** — auditors are single-purpose and report rather than fix; each
  "stays in its lane." Composition over monolithic review.

<!-- FILL IN: Add any principle the code can't reveal — e.g. a stance on how much the
     workflow should ever block vs. only remind. -->

## Feature tracker

Issue tracker: [GitHub Issues](https://github.com/jacquardlabs/studious/issues)

The tracker owns individual features. PRODUCT.md owns strategic context only.

The open issues encode a tiered roadmap with a pre-recorded gate verdict on each:
- **A-tier (Horizon 1)** — foundational: A1 self-verification harness (#24, the
  "keystone"), A2 non-web product support (#25, resolved this cycle), A3 idiom
  feedback loop (#26).
- **M-tier (Horizon 2)** — gate ledger/statefulness (#27), metrics persistence (#28),
  design-doc contract (#29), CI-mode audit (#30).
- **X-tier (moonshot)** — spec traceability (#31), post-ship outcome gate (#32),
  self-tuning corpus (#33), org portfolio health (#34, parked).

## Critical user journeys

Traced from the commands and the README's two-rhythm description.

1. **Initialize** — `/studious-init` > extract PRODUCT.md and DESIGN.md from the
   codebase as it actually is > scaffold `docs/studious/` review directories > wire the
   workflow reference into CLAUDE.md > user reviews PRODUCT.md first (principles and
   "not building" need a human pass).

2. **Per-feature gate flow** — `/backlog-priorities` or `/gate-should-we-build [idea]`
   > design doc > `/gate-design-review` > build with your own workflow > `/gate-audit`
   (6 parallel auditors, frontend lanes auto-skip on diffs with no frontend changes)
   > `/gate-acceptance` > merge. Each gate catches a specific failure; the user skips
   gates the risk doesn't warrant.

3. **Per-project health loop** — `/deep-review` dispatches 5 review agents against main
   in parallel, compiles a cross-referenced master summary with a prioritized action
   plan, and proposes (never applies) updates to the context docs. `/backlog-hygiene`
   then flags resolved/obsolete/duplicated issues against the cycle's fixes.

## What we're NOT building

**Explicitly out of scope (documented):**
- **The *how* of building** — brainstorming, planning, TDD, debugging, and execution
  are deferred to Superpowers. The README states this division repeatedly. Studious
  "steps back here."
- **Auto-applying changes** — reviews and gates propose; they never modify context
  docs or fix code. The human approves every change.
- **Replacing the issue tracker** — Studious works *with* GitHub Issues via `gh`; it
  does not own per-feature state in PRODUCT.md when a tracker is active.

**Likely out of scope (inferred):**
- A monetization/billing layer — none exists; the product is MIT open-source.
- A hosted service or dashboard — the product is entirely local markdown
  commands/agents run inside Claude Code.

**Resolved gap (was #25):** DESIGN.md and the extraction workflow were web-UI-centric
until this change generalized them to detect the product's actual interface surfaces
(web, CLI, TUI, API, plugin) and extract conventions per surface. Non-web products
(backend, data, ML, CLI/plugin, TUI) are now first-class. The web-only UX/a11y audit
lanes still skip cleanly on non-web projects, by design.

## Current known problems

The GitHub tracker is the authoritative source. Ordered here by likely user impact:

1. **The quality tool has no quality gate on itself** (#24) — the entire system is
   markdown prompts, but CI only cuts releases: no markdown lint, no plugin-schema
   validation, no link-check that referenced agents/skills exist, no golden-fixture
   behavioral tests. Gate-contract regressions are caught only by manual audit. The
   maintainer calls this the "highest-leverage gap" and "keystone."
2. **Gates are stateless** (#27) — nothing records that a gate ran or what it
   returned, so the PR-time hook can only ask blindly instead of "acceptance never ran
   on this branch."
3. **No real trend tracking** (#28) — deep-review emits a metrics table but nothing
   persists snapshots across runs, so trends are manual.
4. **The design-doc contract is undefined** (#29) — `/gate-design-review` consumes a
   design doc whose required shape isn't specified.
5. **PRODUCT.md was empty until now** — the project did not fully dogfood its own
   init; this file is the first evidence-based pass and still needs the human review
   the workflow prescribes.

## Business model

No monetization logic found in the codebase. Studious is MIT-licensed, open-source,
and distributed free via the Jacquard Labs Claude Code marketplace. There are no
payment integrations, plan tiers, usage limits, or billing models. It appears to be a
developer-tools / community project rather than a commercial product.

---

## Confidence summary

- **High confidence** (explicit documentation / clear code patterns): why the product
  exists, the gate and review flows, the Superpowers boundary, propose-don't-apply,
  the active GitHub tracker and its roadmap, business model, known problems (sourced
  from the tracker).
- **Medium confidence** (inferred from code structure, naming, and command
  assumptions): the primary persona (feature-branch developer on GitHub with Claude
  Code), the inferred out-of-scope boundaries.
- **Low confidence / needs your input**: product principles (drafted from observed
  behavior — confirm they match intent and add any the code can't reveal), the
  secondary-persona / team-vs-individual question, and any intended boundary on how
  much a gate should ever block versus only remind.
