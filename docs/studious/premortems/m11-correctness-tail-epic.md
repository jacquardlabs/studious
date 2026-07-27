# Pre-mortem — epic `m11-correctness-tail`

Epic: M11 — Correctness & bug tail (17 open issues, 11 stories)
Branch: `epic/m11-correctness-tail`
Recorded: 2026-07-26, at plan approval, before any story dispatched.

Assume the epic shipped and something went wrong. Each mode below names what
would have failed, how it would show up, and what the story that owns it must do
to keep it from happening. `@agent-premortem-auditor` verifies each against the
finished changeset at the finale and returns REALIZED / NOT REALIZED / CAN'T VERIFY.

---

## 1 · The fix for the grammar bug re-diverges the grammar

**Owner:** `verify-tier-grammar` (#208) · **Verifier:** `planparse-grammar-convergence` (#206)

`scripts/plan-lint` accepts a tier spec that `scripts/verify` executes differently.
This is not hypothetical symmetry — it is precisely the bug class #206 describes,
reintroduced by the story meant to fix its sibling. The `::test_name` suffix has to
be parsed twice: once by `plan-lint`'s `check_item_tier` (which must still find the
file, reading only the text before `::`) and once by `verify`'s item derivation
(which must build a runnable command). `TIER_BODY_RE` lives at
`scripts/_planparse.py:40` and is imported by both, so the shared home exists —
the failure is a story that adds suffix handling in one consumer instead of the
shared regex.

**Realized if:** suffix parsing appears in `plan-lint` or `verify` rather than in
`_planparse`, or a plan exists that one accepts and the other mis-executes.

## 2 · The convergence story silently changes an exit code a caller depends on

**Owner:** `script-cli-conventions` (#222, trimmed)

The 0/1/2 ladder is a real convention with no written statement and no test. The
trim answered at interview keeps the `main()` rewrites out of this epic, which
removes most of this risk — but the DESIGN.md paragraph is now normative prose
describing behavior nothing verifies. If the paragraph states a ladder the eight
scripts do not actually implement, the epic ships a documented contract that is
false on arrival, and the next script is held to the wrong thing.

**Realized if:** the DESIGN.md paragraph asserts an exit code any of the eight
scripts does not return, or lands with no test pinning at least the refusal (1)
and usage (2) paths.

## 3 · The new evidence path breaks `/finish`'s reader

**Owner:** `evidence-path-integrity` (#179)

`skills/finish/SKILL.md` reads `docs/jig/evidence/<date>-<task>/` to build the PR
evidence table. Inserting a branch slug changes that shape. A story that fixes the
collision without updating the reader produces PR bodies with dead evidence links —
worse than the collision, because a wrong link reads as verified.

**Realized if:** the path shape changes and `skills/finish/SKILL.md` (or whatever
resolves evidence folders) still matches only the old shape, or no test covers a
`/finish`-side read of a slug-bearing path.

## 4 · An extraction changes which lane certifies SHIP

**Owner:** `epic-driver-decomposition` (#169, #170)

`acceptanceRound` decides which lane certifies `SHIP`. Two prior fix commits landed
as more branching inside it rather than extraction, which is how it reached ~235
lines. Extracting four independently-mutated locals into one result object is
exactly the refactor most likely to change behavior while reading as structural:
a lane that previously fell through to `missing` now returns a populated object, or
a `fallbackFailed` flag stops reaching the caller. The issue itself warns the
missing-lane helper must not flatten each branch's load-bearing prose.

**Realized if:** the epic diff changes any lane's certification outcome for an
input the pre-change code handled differently, or a missing-lane message loses
branch-specific prose, or `pytest tests/python -v` needed an assertion relaxed to
pass.

## 5 · A park at the head of the serial lane stalls two thirds of the epic

**Owner:** epic structure · **Trigger:** any judgment verdict on `verify-tier-grammar`

File collisions force `verify-tier-grammar → script-input-hardening →
gitutil-direct-coverage → tests-jig-dedup`, with `planparse-grammar-convergence`
and `script-cli-conventions` also gated behind the head. Six of 11 stories sit
downstream of S1. A RETHINK there parks the epic at 5 landable stories, and the
run reports "5/11 landed" in a way that reads as broad failure rather than one
blocked fork. The interview front-loaded S1's only product fork specifically to
reduce this, but a design-review judgment verdict is still reachable.

**Realized if:** the epic ends with `verify-tier-grammar` parked and ≥4 stories
recorded blocked on it.

## 6 · The dedup story conflicts on merge and parks after one fix attempt

**Owner:** `tests-jig-dedup` (#226)

Extracting `_normalize_ws` touches all 7 files that define it, including
`test_verify.py`, `test_worktree_setup.py`, and `test_build_skill.py` — each of
which `verify-tier-grammar`, `script-input-hardening`, and `gitutil-direct-coverage`
also edit. The DAG serializes them for this reason, but the driver still gets
exactly one `git merge --no-ff` fix attempt before parking. A story that rebases
stale, or that lands while an upstream story is still in flight, parks on conflict
with the work already done.

**Realized if:** `tests-jig-dedup` parks with a merge-abort reason, or lands having
dropped a change one of its three upstream stories made to a shared test file.

## 7 · The provenance story closes with the trend join still forked

**Owner:** `review-provenance` (#220)

The issue names 4 files; there are 8, and it also names
`docs/studious/reviews/metrics.jsonl` as the dashboard's join key without putting
it in scope. Relocating reports while leaving the jig baseline row in
`metrics.jsonl` leaves the next `/deep-review` trending studious against jig's
numbers — the exact failure the issue was filed about, with the visible half
fixed and the load-bearing half untouched.

**Realized if:** fewer than 8 reports move, or `docs/studious/reviews/metrics.jsonl`
still carries the 2026-07-17 jig row at the finale.

## 8 · A gate-surface story trips gate independence

**Owner:** `epic-driver-decomposition`, `worktree-path-owner`

`workflows/epic-driver.js`, `bin/gate-ledger`, and `commands/*` are the surface
`scripts/check_gate_independence.py` guards: nothing there may invoke a build skill
or require a build artifact (`PLAN.md`, `docs/jig/evidence/`). An extraction that
hardcodes an evidence path as a convenience constant, or a worktree helper that
grows a build-artifact assumption, fails CI rather than the gate — which is the
guard working, but only if the story runs it. Both stories carry
`check_gate_independence.py` in their acceptance criteria for this reason.

**Realized if:** either story's diff introduces a build-skill reference or
build-artifact dependency on the guarded surface, whether or not CI caught it.

---

## Non-goals for this epic, stated so a worker does not drift into them

- `#222`'s four `main()` extractions, error-idiom convergence, refusal-format
  convergence, and `DEFAULT_TIMEOUT_SECONDS` relocation. Deferred at interview;
  #222 stays open carrying them.
- `#200`. Verified obsolete at plan time — README carries a shields.io release
  badge and names no version. Recommend close; no story.
- Unifying `tests/jig/` (stdlib `unittest`) with `tests/python/` (pytest). Two
  runners are deliberate per CLAUDE.md; `tests-jig-dedup` is scoped to `tests/jig/`.
- `run()`'s split between `scripts/_gitutil.py` and `tests/jig/_tempgit.py`.
  #226 says the stated reason still holds; leave it.
