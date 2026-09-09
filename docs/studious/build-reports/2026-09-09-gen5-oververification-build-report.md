# Build report — gen5-oververification (m1-gate-build-cost, #302)

Branch `build/gen5-oververification-202609090019` → `epic/m1-gate-build-cost--gen5-oververification` → `epic/m1-gate-build-cost`. Verdict `MERGE`. Design gate skipped by ruling (2026-09-08); spec = epic ledger criteria + decisions, per #302's 2026-09-07 re-audit.

## Verdict trail

| Episode | Verdict | Sha | Readout |
|---|---|---|---|
| audit (work) | PASS | 8dec7ec | round 1 of 2 — 0 open, 6 carried (0 Critical, 8 Important, 6 Track from 7 lanes) |
| acceptance (delivery) | SHIP | 8dec7ec | round 1 of 2 — 0 open, 5 carried |

Every carried Important was fixed pre-merge in one confirmed dispatch (07ee380) — no re-review under the only-Criticals-block rule; verify re-run green on the fixed tree.

## Evidence — Task 1 (`verify` 5/5 PASS at 8dec7ec; re-run 5/5 at 07ee380; evidence-freshness 1/1 PASS)

| # | Done means | Tier | Evidence | Pass |
|---|---|---|---|---|
| 1 | CONTRIBUTING.md carries the verification invariant beside the bookkeeping/judgment rule, with a disposition table naming all three sites | test-backed `tests/python/test_verification_invariant.py` | pytest exit 0 | PASS |
| 2 | Pillar 3 cites #188 as the gate on its deletion — moved to CONTRIBUTING's KEEP PENDING row in the fix (the runtime prompt no longer carries maintainer bookkeeping) | test-backed `tests/python/test_verification_invariant.py` | pytest exit 0 | PASS |
| 3 | No prompt file under agents/, commands/, skills/, reference/ contains a self-check phrase outside the (empty) allowlist | test-backed `tests/python/test_verification_invariant.py` | pytest exit 0; non-vacuity and positive-match guards added in the fix | PASS |
| 4 | Existing prose pins on the discipline skill still pass | script `tests/jig/test_discipline_skill.py` | exit 0 | PASS |
| 5 | markdownlint and the reference link-check still pass | script `scripts/check_references.py` | exit 0 | PASS |

`verify` ran under `uv run --with pytest` (#248). Inspector skipped: leaf task.

## Exorcise

Dispatch stopped: the subagent entered a runaway wait loop (73 backgrounded `sleep` commands while polling its own lanes). Partial edit discarded per `/build` Step 3.7; Track note, nothing cast out. Feedback drafted for the Claude Code team.

## Dispositions (#302)

`reference/audit-compilation.md` Critical challenge — KEEP (judgment routing, carve-out). `reference/prompt-contract.md` §4 — MOOT (#334 S4 deletes it; #404 retires the row then). `skills/task-execution-discipline/SKILL.md` Pillar 3 — KEEP PENDING #188 (nothing deleted, so `scripts/run_gate_audit_fixtures.py` was not run; the M1 cost effect of this story is zero tokens saved, by the decision record).

## cctx

Not installed; no session-cost footer.

## Follow-ups filed

#404 retire the prompt-contract MOOT row and its pin when #334 S4 lands (and update the 22 agent fallbacks that still cite the file).
