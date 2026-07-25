# /finish report — epic/m3-plan-skill

## Scope deviation from `/finish`'s literal spec

This branch was not produced by jig's own `/build` loop — `plan-lint` and
`plan-skill` were built via studious's `/work-through` epic-driver, using
its generic worker-contract (a design doc + direct implementation), not a
top-level `PLAN.md`. There is no `PLAN.md` at this branch's root and no
`docs/jig/evidence/<date>-<task>/` folders, so **Step 1's Done-means
evidence table has no input to assemble and was skipped**, by explicit
confirmation. The equivalent evidence exists in a different shape:
studious's own epic-finale audit (`PASS`) and acceptance (`SHIP`) verdicts,
and the pre-mortem verification (every item `NOT REALIZED`), all recorded
during `/work-through`'s finale on 2026-07-16.

**Step 6's cleanup was also skipped**, by explicit confirmation, for the
same root cause: that cleanup is normally safe because Step 1 already
promoted `docs/design/*.md` and the demo folder's substance into the PR
body first. With Step 1 skipped, deleting them now would be pure loss —
`docs/design/plan-lint.md`, `plan-lint-ci.md`, `plan-skill.md`, and
`docs/jig/demonstrations/2026-07-16-plan-skill/` (including the live viva
sign-off evidence: `ci-wiring-demo/viva-round-trip/live-signoff-review-
input-r1.json` / `live-signoff-review-r1.json`) are kept in place on this
branch rather than removed.

## Step 2 — cctx footer

`cctx` is not installed in this environment. Skipped the session-cost
footer and harvest offer. Install with `pipx install cctx-cli` to populate
this step on a future `/finish` run.

## Step 3 — File survivors

No top-level `PLAN.md` exists for this epic, so there is no real "##
Not-here follow-ups" list in the normal sense. Two real sources stood in
for it instead, presented per-item and all four accepted:

1. **[jig#66](https://github.com/jacquardlabs/jig/issues/66)** — Add an
   integration test binding `/plan`'s `--split-on`, `plan-lint`'s
   `split_tasks`, and `/build`'s Step 1.4 boundary rule. Source: epic
   finale audit (architecture-auditor lane), Important tier.
2. **[jig#67](https://github.com/jacquardlabs/jig/issues/67)** — Add a
   release-blocking status-check requirement on `main`'s branch ruleset.
   Source: `ci-wiring-demo/PLAN.md`'s own Not-here list (demo-sourced, not
   built as product work in this epic).
3. **[jig#68](https://github.com/jacquardlabs/jig/issues/68)** — Lint a
   `/plan`-authored `PLAN.md` itself in CI, once a story routinely commits
   one as evidence. Source: same demo fixture.
4. **[jig#69](https://github.com/jacquardlabs/jig/issues/69)** — Add a
   type-checking job to CI. Source: same demo fixture; needs a prior
   tooling decision since `CLAUDE.md` names no type checker today.

**NOTES stubs**: 0 found. `/build`'s current implementation does not yet
write these (no NOTES-stub step exists in `skills/build/SKILL.md` today) —
an honest, not a broken, result.

## Step 4 — Proposed decision patch (never applied)

The #23 resolution — keeping the `##` heading for `Not-here follow-ups`
and using an explicit viva `--split-on` pattern instead of the issue's
literal `####`-heading suggestion — is a ruled fork with lasting
consequences that was not yet documented in `DESIGN.md`. Proposed diff
(copy in by hand; nothing here was applied):

```diff
   A backtick span anywhere in a checkpoint block (a `Read first:` pointer, a
   tier's method path, a `[cap]` item's own behavior text on a LOAD-BEARING
   task) is the plan author's explicit signal that a token is concrete and
   checkable, not narrative — `scripts/plan-lint` treats prose outside
   backticks as unchecked by design.
+- **`/plan`'s viva invocation always passes an explicit `--split-on`**
+  (`(?i)^(Task \d+|Not-here follow-ups|Revision History)`), never bare
+  auto-detect (issue #23) — two collision risks auto-detect alone doesn't
+  cover: viva's own `revision_history.py` appends a second `##`-level
+  heading at sign-off, and a re-parsed already-signed-off doc then carries
+  two singleton `##` headings, which retriggers auto-detect's "coarsest
+  level that repeats more than once" heuristic at level 2 instead of 3 —
+  collapsing every task card into one merge. **The heading level for
+  `Not-here follow-ups` stays `##`, unchanged** — issue #23's own literal
+  suggestion (a finer `####`) was deliberately not adopted: it would nest
+  *inside* the preceding task under `/build`'s and `plan-lint`'s existing
+  level-1-3 boundary rule, silently reproducing the exact absorption bug
+  this decision closes. The `--split-on` pattern, not a heading-level
+  change, is what actually fixes it.
 - **Design doc structure** (handoff §5.1 step 4): 5-8 sections, each tied to
   a named downstream consumer (Intent, Experience, Contracts, Approach,
   Assumptions, Not doing, Risks — see the section→consumer table in §5.1).
```

## Step 6 — Verdict

**PR**. Target branch: `main` (resolved with confidence — `epic/m3-plan-
skill` has no upstream tracking and demonstrably diverged from `main` at
`73b2c81`; no `<parent>--<story>` naming to override it).
