# Product context

## Why this product exists

jig is a Claude Code plugin that owns the **build** step of feature
development — the slot where [studious](https://github.com/jacquardlabs/studious)
currently says "build it with your own workflow" and users reach for
Superpowers instead. Evidence: README.md's opening framing, and the
project's handoff document (distilled from a July 2026 research + design
session covering the agentic-workflow landscape — Superpowers, BMAD, pstack,
mattpocock/skills, spec-kit/Kiro, Gas Town — and the jacquardlabs portfolio).

The origin story, per that document: studious's identity is judgment (the
*what* and *whether*); it explicitly steps back at build time. jig fills
that gap as a sibling plugin — not merged into studious (which would break
studious's promise to users who pair it with other build workflows), and not
a standalone platform (the orchestration tier of the market is
commoditizing; the durable value is process structure that lets
cheaper/current models perform above their tier).

**Confidence: high** — sourced directly from the ratified handoff document
and README.md, not inferred.

## Who uses it

### Primary persona

A developer using Claude Code, likely already pairing it with studious's
judgment gates, who wants a repeatable, verifiable build/implementation
workflow instead of ad hoc prompting or Superpowers. Evidence: the
portfolio-relationship table in README.md positions jig strictly as the
"execution" layer, consumed after studious's `/gate-design-review` and
before its `/gate-audit`/`/gate-acceptance`.

### Secondary persona (if applicable)

A Claude Code user with no other jacquardlabs tooling installed at all.
Evidence: design principle 10, "Standalone-capable" — every degradation
without studious/viva/cctx installed is graceful (e.g. `/finish` ends at
"branch ready for your review" instead of handing to `/gate-audit`), which
only matters if this persona is real.

**Confidence: medium** — the primary persona is well-evidenced; the
secondary persona is inferred from a design principle rather than directly
stated.

## Product principles

<!-- FILL IN: the handoff document ratifies 11 non-negotiable principles
     (§2) — more than the 3-5 this section calls for. The 5 below were
     selected as the most product-shaping; confirm this is the right
     subset to lead with, or promote different ones from the full list. -->

- **Judgment in the model, mechanics in scripts** — anything decidable
  without judgment (status flips, verification runs, lints, evidence
  capture) is a script; the model never self-reports what a script can
  check.
- **Recommend one action; the human decides. Propose; never apply** —
  applies to next-step recommendations, context-doc updates, and plan
  revisions alike.
- **Nothing signs off on itself** — executor attestation is structurally
  worthless; scripts re-verify everything; independent fresh-context review
  at boundaries.
- **Standalone-capable** — every degradation without a sibling plugin
  installed is graceful; none is silent.
- **Anti-cleverness tripwire** — sequential for-loop is the default; no
  named agent personas, no sprint ceremony, no resident coordinating roles.

**Confidence: low / needs your input** — these are the ratified principles
verbatim, but the *selection* of which 5 lead is an editorial judgment call
this document flags rather than makes unilaterally.

## Feature tracker

Issue tracker: [GitHub Issues](https://github.com/jacquardlabs/jig)

The tracker owns individual features (milestones M0–M6, all complete as of
v1.6.0). This section intentionally doesn't duplicate that inventory or
hardcode an issue count that would immediately go stale.

**Confidence: high** — GitHub Issues is active and populated; verified via
`gh issue list`.

## Critical user journeys

All five skills shipped (M1–M6 complete, current release v1.6.0) and these
journeys are observable in a running product, not just committed design —
each skill's own `SKILL.md` is the source of truth (see DESIGN.md's
Vocabulary table).

1. **Full cycle:** `/gate-should-we-build` (studious) → `/design` (batch
   interview → forks → sectioned doc → viva) → `/gate-design-review`
   (studious) → `/plan` (inventory → spine → checkpoint blocks → viva) →
   `/build` (fresh executor per task, script-verified, conditional
   inspector) → `/gate-audit` → `/gate-acceptance` (studious) → `/finish`
   (PR evidence table, cctx harvest, follow-ups, cleanup).
2. **Quick path** (small fixes / most bugs): a single task block straight to
   `/build`, then `/gate-audit`.
3. **Revision loop:** an `ESCALATE` verdict from `/build` returns to
   `/design` in revision mode; a `REVISED` doc re-enters `/gate-design-review`
   for a full persona walk. `/coach` (M6) is the user-invoked entry point for
   re-entering this loop from a `PAUSED` or `ESCALATED` state.

**Confidence: high** — every skill named here has shipped, real behavior
(`skills/*/SKILL.md`, none stubs), demonstrated across the CHANGELOG's
v1.0.0–v1.6.0 releases, and each skill's own test suite
(`tests/test_*_skill.py`) exercises this journey's verdict paths.

## What we're NOT building

Directly from the handoff document's ratified decision (v1 or ever):

- Named agent personas, sprint ceremony, or retrospective agents (a driver
  of BMAD's abandonment, per the research this project cites)
- A permanent spec corpus beyond the three context docs (PRODUCT.md,
  DESIGN.md, CLAUDE.md) — no fourth document class, no ADR corpus
- Fleet orchestration, resident monitors, work ledgers, or health-monitor
  roles
- In-loop review beyond the conditional rough-in inspector
- Judgment-tier checkpoint items in `/build` (those belong to studious's
  gates)
- A plan the loop can amend under its own failure pressure
- Fan-out beyond "N independent loops + a selector" — no tournament
  brackets, no candidate cross-pollination, no plan-level competition

**Confidence: high** — this is an explicit, itemized list in the ratified
handoff, not inferred.

## Current known problems

All five skills have shipped and are in active use; the M0-era blockers
this section used to list are resolved (viva#101, #112, #113, #115, and
jig #23 are all closed — see `docs/jig/dogfood/FRICTION-REPORT.md` on
branch `docs/m0-paper-dogfood` for the historical record of what M0's paper
dogfood surfaced). Current open bugs, per `gh issue list --label bug`:

- [#36](https://github.com/jacquardlabs/jig/issues/36) — `pyproject.toml`'s
  Ruff config uses `select` instead of `extend-select`, silently disabling
  Pyflakes and default pycodestyle checks.
- [#46](https://github.com/jacquardlabs/jig/issues/46) — the build design
  doc doesn't document the evidence-dir-commit step before `status-flip`
  that a real dogfood run showed is required (skipping it stalls task 2 of
  any multi-task plan).
- [#71](https://github.com/jacquardlabs/jig/issues/71) — `docs/design/*.md`
  files are force-added and never stripped before merge, despite the
  project's own "design docs die at merge" convention.

Broader engineering debt (idiom drift, fragile vocabulary derivation, test
gaps) is tracked as ordinary open issues, not duplicated here — see the
[issue tracker](https://github.com/jacquardlabs/jig/issues).

**Confidence: high** — sourced directly from `gh issue list --label bug`
and each issue's own body, not speculation.

## Business model

No monetization logic exists or is planned. jig is MIT-licensed and free,
matching every sibling plugin in the jacquardlabs portfolio (studious, viva,
cctx, voice-suite, etc.) — all public, all free.

**Confidence: high** — consistent with the LICENSE file and the entire
portfolio's existing pattern; no payment integration or pricing logic
exists to contradict this.
