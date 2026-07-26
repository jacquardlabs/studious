# Product health review — 2026-07-17

## Summary

jig reads as **one coherent product**, not a bag of features: the five
user-invoked skills (`/design → /plan → /build → /finish`, tied together by
`/coach`) implement a single named pipeline, and `/coach` (M6) gives a new
user a 60-second entry point that reads pipeline state and recommends one
action. PRODUCT.md was re-extracted today (#86) and is materially accurate —
personas are stable, the known-problems list is an exact match to open bug
issues, and the Feature-tracker section correctly defers to GitHub Issues
rather than carrying a stale feature map. Biggest strength: doc/tracker
discipline — no sync hazard, no invented feature inventory. Biggest drift is
soft: PRODUCT.md's "no named agent personas" principle reads, on its face, as
contradicting `/build`'s own Foreman/Executor/Inspector role language, and a
6-issue model-routing/telemetry thread is building in the tracker with zero
visibility from PRODUCT.md.

## Critical

None. PRODUCT.md does not actively mislead, and product coherence is intact.

## Important

| # | severity | location | dimension | finding | confidence | recommendation |
|---|----------|----------|-----------|---------|------------|----------------|
| I1 | Important | PRODUCT.md §Product principles L66-67 "Anti-cleverness tripwire … no named agent personas" (and §What we're NOT building L112-113) | Principles check | Core principle reads as contradicting `/build`'s flagship language "You are the **Foreman** … dispatch a fresh **Executor** … **Inspector**" (skills/build/SKILL.md L8-27) | Confirmed | Sharpen the principle to name the distinction the skill already draws: functional, ephemeral session roles (Foreman/Executor/Inspector) are permitted; prohibited "named agent personas" are resident, anthropomorphized, BMAD-style roles. Without this, a contributor reads a live contradiction. |

## Track

| # | severity | location | dimension | finding | confidence | recommendation |
|---|----------|----------|-----------|---------|------------|----------------|
| T1 | Track | PRODUCT.md — no mention anywhere | Feature inventory / coherence | 6 open issues (#22, #33, #40, #41, #42, #43) build toward per-stage model routing, a routing-table contract, a replay harness, and dispatch telemetry — a substantial forward direction invisible from PRODUCT.md | Confirmed | Not out of scope (serves the "let cheaper/current models perform above their tier" thesis, L18-19), but PRODUCT.md gives a new contributor zero visibility. Consider a short "Directions under evaluation" pointer to the tracker, or fold into Critical user journeys once #43's speed/price audit lands. |
| T2 | Track | README.md L20, L129 "current release is v1.5.0" | Cross-doc coherence | README stale at v1.5.0; latest release and PRODUCT.md both say v1.6.0 (confirmed via `gh release list`) | Confirmed | Not a PRODUCT.md defect (PRODUCT.md is correct) — route to `/deep-review readme`. Flagged here only because it is product-facing surface a new user hits first. |
| T3 | Track | PRODUCT.md L86 "All five skills"; README L7-8 "Five user-invoked skills" | Feature inventory | `skills/` holds six dirs; the sixth, `task-execution-discipline`, is model-invoked discipline (not a slash command) and is unmentioned in PRODUCT.md's journeys, though `/build` invokes it (SKILL.md L246) | Confirmed | "Five user-invoked skills" is a defensible framing. Confirm the omission is intentional; if `task-execution-discipline` is load-bearing to the build journey, name it once in Critical user journey #1. |
| T4 | Track | PRODUCT.md L67 "sequential for-loop is the default"; open issue #83 | "Not building" / watch-item | Issue #83 (parallel executors) is deferred behind #43/#74 — sits within "default" (not "only"), so not a violation, but worth watching against the sequential-loop invariant `/build` asserts ("never in parallel", SKILL.md L40) | Confirmed | No action this cycle. Re-check next cycle: if #83 advances, verify the "default" wording still holds and that graceful-degradation / determinism principles survive parallelism. |

## Product-health signals

- **shipped-but-undocumented features** — 0 (`task-execution-discipline` is internal discipline referenced by `/build`, not a user-facing feature; logged as T3, not counted)
- **"not building" violations** — 0 (checked open issues: #16 fan-out = the *allowed* "N independent loops + a selector", not the forbidden tournament/cross-pollination; model-routing issues serve the stated thesis)
- **stale known-problems** (fixed but still listed) — 0 (PRODUCT.md lists #36, #46, #71; `gh issue list --label bug` returns exactly #36, #46, #71 — all still open)
- **persona-drift** — stable (M2–M6 built precisely the studious-paired build pipeline of the primary persona; principle-10 graceful degradation for the standalone secondary persona is live in every skill description)

## Trend vs last cycle

Baseline — `docs/studious/product-reviews/` held only `.gitkeep`; no prior reports. All signals recorded fresh for future comparison.

## Proposed PRODUCT.md diff

```diff
@@ ## Product principles @@
 - **Anti-cleverness tripwire** — sequential for-loop is the default; no
-  named agent personas, no sprint ceremony, no resident coordinating roles.
+  named agent personas, no sprint ceremony, no resident coordinating roles.
+  (Functional, ephemeral session roles — the Foreman/Executor/Inspector a
+  single `/build` loop dispatches one at a time — are not "personas": they
+  are not resident, not anthropomorphized, and hold no state across tasks.
+  The prohibition targets BMAD-style named resident agents, not role labels
+  on a for-loop's stages.)
```

Optional (T1 direction, only if you want forward visibility in the doc rather
than the tracker): add a one-line "Directions under evaluation" note after
Critical user journeys pointing at the model-routing/telemetry issue cluster
(#22, #33, #40–#43) as evidence-gated, not-yet-committed scope. Left out of
the diff above because the tracker already owns it and PRODUCT.md deliberately
avoids duplicating tracker state.

All other sections — personas, "what we're NOT building", known problems,
business model, Feature-tracker — verified accurate; no changes proposed.

## Residual line

Verified clean: known-problems list (exact match to open bugs), persona
alignment against M2–M6 commit history, no stale feature map (tracker
correctly owns inventory), no "not building" violations in open issues, MIT
business-model claim against LICENSE. Read-only throughout — `git log`,
`gh issue/release list`, and file reads only; no build/test/install run.
Limitation: skill *behavior* was assessed from SKILL.md descriptions and the
build loop's prose, not by executing any skill; GitHub Issues timestamps
show as 2026-07-18Z (tomorrow local) — a timezone artifact, not a data issue.
