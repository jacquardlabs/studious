# Build report — persist a replay bundle per build task (issue #34)

Branch `build/replay-bundle-202607170239`, 4 tasks, both gates clean (`/gate-audit` PASS, `/gate-acceptance` SHIP after one FIX AND RE-CHECK cycle).

## PR evidence table

| # | Item | Method | Evidence | Pass |
|---|---|---|---|---|
| T1.1 | `skills/build/SKILL.md` step 2's dispatch text names which model the Executor runs on, distinguishing an explicit `override` from the `inherited` case, immediately beside the existing dispatch-timestamp capture | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-1/results.json` | PASS |
| T1.2 [hold] | the existing dispatch-timestamp and boundary-line phrase assertions in `tests/test_build_skill.py` still pass unchanged | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-1/results.json` | PASS |
| T2.1 | step 7's new instruction states the bundle is assembled at a scratch path (never inside the worktree first) before the existing evidence-capture call, naming all four fields | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-2/results.json` | PASS |
| T2.2 | step 7's new instruction states the one additional `--artifact build:replay-bundle=<scratch-path>/replay-bundle.json` flag added to the existing evidence-capture call, not a second invocation | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-2/results.json` | PASS |
| T2.3 [hold] | the existing step 7 phrase assertions (`verify:results` artifact call, commit-before-status-flip ordering) still pass unchanged | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-2/results.json` | PASS |
| T3.1 | step 2's dispatch-model instruction names a third case, `unavailable`, for when the model genuinely can't be determined, immediately beside `override`/`inherited` | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-3/results.json` | PASS |
| T3.2 | step 7's bundle-assembly instruction states that an `unavailable` value is written into the bundle rather than refusing the `evidence-capture` call | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-3/results.json` | PASS |
| T3.3 [hold] | the existing step 2 and step 7 phrase assertions (`override`/`inherited` cases, four-field bundle, single `--artifact` flag) still pass unchanged | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-3/results.json` | PASS |
| T4.1 | step 1.5's text names the plan-growth case: a new task's `Rests on:` line naming an already-`PASS`ed task triggers an immediate load-bearing-set recompute | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-4/results.json` | PASS |
| T4.2 | step 1.5's text states that a task whose status changes from leaf to load-bearing under the recompute, having already reached `PASS` without an Inspector, gets a retroactive catch-up Inspector dispatched now | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-4/results.json` | PASS |
| T4.3 | step 1.5's text names the sanctioned evidence-dir naming convention for a retroactive catch-up inspection, `<task>-retroactive-inspection`, and states why the task's own original evidence folder isn't reused | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-4/results.json` | PASS |
| T4.4 [hold] | the existing step 1.5 "compute once... before task 1 is ever dispatched" phrase assertions still pass unchanged | test-backed `tests/test_build_skill.py` | `docs/jig/evidence/2026-07-17-4/results.json` | PASS |

**Freshness hold**: `scripts/evidence-freshness` re-validated all 5 evidence folders (including the retroactive-inspection addendum below) against their own recorded `manifest.json` commits — 5/5 PASS.

**Inspection record** (not a `Done means` item, supplementary provenance):
- Task 1 (load-bearing): fresh Inspector dispatched after its own `verify` PASS — verdict **CLEAR** (`docs/jig/evidence/2026-07-17-1/report.md`).
- Task 2 (originally a leaf, retroactively made load-bearing by Task 3's `Rests on:` line): a catch-up Inspector was dispatched against Task 2's own original commit (`246766b`) before Task 3 was built on top of it — verdict **CLEAR** (`docs/jig/evidence/2026-07-17-2-retroactive-inspection/report.md`). Captured under its own evidence-dir ID rather than reusing Task 2's original folder, since `evidence-capture` always stamps against current `HEAD` and reusing the original folder would have misdated the inspection against a later, unrelated commit. Task 4 (this same branch) formalized this exact recompute-and-retroactively-inspect path into `skills/build/SKILL.md` step 1.5 itself.
- Task 3 and Task 4 (leaves): no other task's `Rests on:` names either — Inspector correctly skipped for both.

### Evidence detail

<details>
<summary>T1.1 — dispatch-model text (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_dispatch_names_the_executor_model_beside_the_timestamp_capture -v
exit code: 0
test_dispatch_names_the_executor_model_beside_the_timestamp_capture ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T1.2 — pre-existing dispatch-timestamp/boundary-line assertions (hold)</summary>

Full suite, 324 tests, `OK (skipped=1)` — the pre-existing single unrelated skip (PyYAML not installed). Every pre-existing `test_build_skill.py` assertion (dispatch-timestamp capture, boundary-line phrasing, all four scripts named, all four roles named, etc.) passed unchanged alongside Task 1's own new test.
</details>

<details>
<summary>T2.1 — bundle assembled at scratch path (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture -v
exit code: 0
test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T2.2 — single --artifact flag, no second invocation (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_7_replay_bundle_rides_the_existing_evidence_capture_call -v
exit code: 0
test_step_7_replay_bundle_rides_the_existing_evidence_capture_call ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T2.3 — pre-existing step 7 assertions unchanged (hold)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_evidence_directory_is_committed_before_status_flip -k test_step_7_evidence_capture_points_at_the_scratch_path_results -v
exit code: 0
test_evidence_directory_is_committed_before_status_flip ... ok
test_step_7_evidence_capture_points_at_the_scratch_path_results ... ok

Ran 2 tests in 0.002s
OK
```
</details>

<details>
<summary>T3.1 — unavailable case named at step 2 (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_dispatch_model_names_unavailable_case_beside_override_and_inherited -v
exit code: 0
test_dispatch_model_names_unavailable_case_beside_override_and_inherited ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T3.2 — unavailable case at step 7 (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_7_bundle_assembly_writes_unavailable_rather_than_refusing_capture -v
exit code: 0
test_step_7_bundle_assembly_writes_unavailable_rather_than_refusing_capture ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T3.3 — pre-existing Task 1/Task 2 assertions unchanged (hold)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_dispatch_names_the_executor_model_beside_the_timestamp_capture -k test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture -k test_step_7_replay_bundle_rides_the_existing_evidence_capture_call -v
exit code: 0
test_dispatch_names_the_executor_model_beside_the_timestamp_capture ... ok
test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture ... ok
test_step_7_replay_bundle_rides_the_existing_evidence_capture_call ... ok

Ran 3 tests in 0.002s
OK
```
</details>

<details>
<summary>T4.1 — plan-growth recompute trigger named (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_1_5_names_plan_growth_recompute_trigger -v
exit code: 0
test_step_1_5_names_plan_growth_recompute_trigger ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T4.2 — retroactive catch-up Inspector named (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_1_5_names_retroactive_catch_up_inspector -v
exit code: 0
test_step_1_5_names_retroactive_catch_up_inspector ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T4.3 — retroactive-inspection evidence-dir convention named (cap)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_step_1_5_names_retroactive_inspection_evidence_dir_convention -v
exit code: 0
test_step_1_5_names_retroactive_inspection_evidence_dir_convention ... ok

Ran 1 test in 0.001s
OK
```
</details>

<details>
<summary>T4.4 — pre-existing "compute once" assertion unchanged (hold)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -k test_load_bearing_set_is_computed_once_after_the_task_split -v
exit code: 0
test_load_bearing_set_is_computed_once_after_the_task_split ... ok

Ran 1 test in 0.001s
OK
```
</details>

**Final full-suite state**: 331 tests, `OK (skipped=1)` — the one pre-existing unrelated skip, unchanged throughout this branch.

## Gate history

| Gate | Verdict | Notes |
|---|---|---|
| `/gate-audit` (round 1) | PASS | 0 Critical; 1 Important (mechanism never executed end-to-end — design-accepted, tracked to a future `/deep-review architecture` pass), several Track findings |
| `/gate-acceptance` (round 1) | FIX AND RE-CHECK | 1 SHOULD FIX: design doc's own Failure path (`unavailable` sentinel) dropped from shipped prose |
| Task 3 | — | Closed the SHOULD FIX |
| `/gate-acceptance` (round 2) | SHIP | Prior SHOULD FIX confirmed closed; 2 OBSERVATIONs only |
| `/gate-audit` (round 2, after Task 3) | PASS | 0 Critical; 3 Important (1 new: step 1.5 has no defined path for a plan growing mid-session; 1 carried forward: mechanism still unexecuted; 1 escalated: design doc's Revision History duplication, Low→Medium); several Track findings |
| Task 4 | — | Closed the new Important finding (step 1.5 plan-growth gap) |

**Not re-run after Task 4**: `/gate-audit` and `/gate-acceptance` were not re-invoked a third time after Task 4 landed, per explicit instruction — Task 4's own diff (3 new tests, one prose paragraph, all `test-backed` and independently `verify`-PASSed) is judged low-risk enough to skip a third full audit cycle.

**Still open, not fixed on this branch**: the `/gate-audit` round-2 Important finding that `docs/design/replay-bundle.md`'s Revision History section has grown to 4 byte-identical duplicate sign-off lines (a recurring `/design` viva-sign-off pattern `design-lint` doesn't check) was not addressed — it wasn't raised again for an explicit fix-or-defer decision before this report was assembled. Flagging here since it's a real, unresolved Important-tier finding, not silently dropped.

## cctx footer

cctx not installed in this environment — skipping the session-cost footer and harvest offer. Install with `pipx install cctx-cli`.

## Follow-ups

**`PLAN.md`'s own `## Not-here follow-ups`** (4 items) — all four already point at existing tracking, so zero new GitHub issues were filed:
- Independent corroboration of the recorded `model` field against cctx's own session-trace export — already deferred to issue #33/cctx#193/#196.
- Issue #33's richer identity fields (`run_id`/`step_id`/`parent_step_id`/`skill`/`role`/`routing_reason`) — already tracked under issue #33.
- The replay harness itself — already tracked under issue #41.
- The viva-qa note-loss bug found during this feature's own `/design` session — already filed as a comment on jacquardlabs/viva#121.

**NOTES stubs**: 0 found — `/build`'s current implementation has no NOTES-stub step, an honest "0 found" rather than an error.

## Decision patches

None proposed. Nothing in this branch's work rises to a lasting decision against `PRODUCT.md`, `DESIGN.md`, or `CLAUDE.md` — the two mechanics fixes this branch made (the `unavailable` sentinel, the plan-growth recompute path) are both scoped entirely inside `skills/build/SKILL.md`'s own prose contract, not a product/design/architecture-level decision those three docs govern.
