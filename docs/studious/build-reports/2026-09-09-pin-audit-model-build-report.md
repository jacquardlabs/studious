# Build report — pin-audit-model (m1-gate-build-cost, #136 reproducibility half)

Branch `build/pin-audit-model-202609082320` → `epic/m1-gate-build-cost--pin-audit-model` → `epic/m1-gate-build-cost`. Verdict `MERGE`. Design gate skipped by ruling (2026-09-08); spec = epic ledger criteria + decisions.

## Verdict trail

| Episode | Verdict | Sha | Readout |
|---|---|---|---|
| audit (work) | PASS | 48b9155 | round 2 of 2 — 0 open, 5 carried (round 1: 1 Critical, 8 Important → one FIX dispatch; round 2 narrowed to code-auditor) |
| acceptance (delivery) | SHIP | 48b9155 | round 1 of 2 — 0 open, 7 carried |

## Evidence — Task 1 (`verify` 5/5 PASS at 3994ff7; evidence-freshness 2/2 PASS)

| # | Done means | Tier | Evidence | Pass |
|---|---|---|---|---|
| 1 | No file under agents/ carries model: inherit; the four formerly-inherit agents carry an explicit model | test-backed `tests/python/test_model_pins.py` | `python3 -m pytest tests/python/test_model_pins.py -q` exit 0 | PASS |
| 2 | Every non-judge agent() dispatch in workflows/epic-driver.js carries a model key | test-backed `tests/python/test_model_pins.py` | same run, exit 0 | PASS |
| 3 | DESIGN.md and CONTRIBUTING.md contain no instruction to use inherit; the inherit bucket is empty | test-backed `tests/python/test_model_pins.py` | same run, exit 0 | PASS |
| 4 | node --check, eslint, workflows lint suite pass | script `tests/test_workflows_lint.sh` | exit 0, 19 cases | PASS |
| 5 | pytest suite passes with the new test | script `tests/test_workflows_lint.sh` (as planned); full suite 935 passed at 48b9155 | exit 0 | PASS |

`verify` ran under `uv run --with pytest` so its derived `python3 -m pytest` resolved (#248's environment gap). Inspector skipped: Task 1 is a leaf.

## Exorcise

`exorcise: _agent_files, FORMERLY_INHERIT, NON_JUDGE_DISPATCH_LABELS` (d2f21f8) — 14 hunks traced, 3 rewritten (single-caller helpers inlined), 0 reverted, 3 held: `MODEL_LINE` duplicating `run_ab_eval.py`'s frontmatter regex; `tests/ab/README.md:158` baseline sentence (fixed in 48b9155); `reference/telemetry-format.md:62` inherit-evidence clause (fixed in 48b9155).

## cctx

Not installed; no session-cost footer (`pipx install cctx-cli`).

## Follow-ups filed

#400 move the reproducibility pin to gauntlet's judge files; scope CONTRIBUTING's merge-blocking claim · #401 driver tier policy: cost direction, fallback, stale opus-reserved comment · #402 harden the model-pin guard · #403 narrow the inherit claim, DESIGN.md ID-vs-alias rule, verify claude-opus-5 resolves before the A/B.

## Decision patch (proposed, not applied)

PRODUCT.md "Shipping our own judge fleet": *"Studious keeps its three local agents"* → *"Studious keeps its local `agents/` files as gauntlet mirrors until #334 S4 retires them; every judge lane dispatches `gauntlet:*`."*

## Deviations recorded in the story's decisions

Driver dispatches pin the `opus` alias (Workflow `agent()` documents no full-ID resolution); scope grew four → five dispatches (exorcise); the four local agent files are mirrors — the merge-gating pins live in gauntlet (#400).
