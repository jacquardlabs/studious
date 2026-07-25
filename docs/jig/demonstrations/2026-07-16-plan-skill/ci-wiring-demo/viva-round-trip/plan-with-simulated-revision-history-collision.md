# Plan: wire scripts/plan-lint (and Ruff) into CI

Drafted by `/plan` (story `plan-skill`) against the real design doc
`docs/design/plan-lint-ci.md`, following Steps 1-4 verbatim, as this
story's required "real `PLAN READY` plan, end to end" demonstration
(`docs/design/plan-skill.md`, Operational readiness, demonstration 1).

Spine: Task 1 -> Task 2 -> Task 3 (each rests on the one before it; the
`test` job lands first since it needs nothing else, the `lint` job is
added to the same file second, and the `CLAUDE.md` caveat can only come
true once the `lint` job is live).

### Task 1 — Add `.github/workflows/ci.yml`'s `test` job
Why now:    no `pull_request`-triggered job runs this repo's own baseline test command today (`.github/workflows/release.yml` triggers on `push`/`workflow_dispatch` only); this is the smaller, independent half of the CI gap and unblocks Task 2's `lint` job addition to the same file.
Read first: `.github/workflows/release.yml`, `CLAUDE.md`
Rests on:   n/a -- first task.
Do:         create `.github/workflows/ci.yml` with a `pull_request`-triggered `test` job that checks out the repo and runs `uv run --no-project python3 -m unittest discover -s tests -v`; extend `tests/test_scaffold.py` with a new `TestCiWorkflow` class asserting the file exists, triggers on `pull_request`, and names the exact baseline command. Note here for Task 2: the same file's `lint` job (added next) will run `ruff check .` and `scripts/plan-lint` against `tests/fixtures/plan-lint/clean-plan.md` and `tests/fixtures/plan-lint/broken-plan.md`.
Not here:   no `lint` job yet (Task 2), no branch-protection ruleset change, no `release.yml` edits.

Done means:
1. [cap]  `.github/workflows/ci.yml` exists, triggers on `pull_request`, and its `test` job runs `uv run --no-project python3 -m unittest discover -s tests -v`   (tier: test-backed `tests/test_scaffold.py`)
2. [hold] `.github/workflows/release.yml`'s own `push`/`workflow_dispatch` triggers are unmodified   (tier: script `.github/workflows/release.yml`)
Evidence: (recorded by scripts/evidence-capture once /build executes this task; none yet -- this plan has not been built)

### Task 2 — Add the `lint` job (Ruff + both plan-lint fixtures) to `.github/workflows/ci.yml`
Why now:    CLAUDE.md's own Linter row and `docs/design/plan-lint.md`'s own Out of scope both name the same unwired gap (Ruff, and separately `scripts/plan-lint`); closing both in one job keeps the CI surface Task 1 established from growing a third, near-duplicate workflow file.
Read first: `pyproject.toml`, `scripts/plan-lint`, `tests/fixtures/plan-lint/clean-plan.md`, `tests/fixtures/plan-lint/broken-plan.md`
Rests on:   Task 1 (the new `lint` job is added to the file Task 1 creates).
Do:         add a `lint` job to `.github/workflows/ci.yml` that runs `ruff check .` and two `scripts/plan-lint` invocations -- one against `tests/fixtures/plan-lint/clean-plan.md` (expected exit 0) and one against `tests/fixtures/plan-lint/broken-plan.md` (expected exit 1, the step scripted so an expected 1 doesn't fail the job); extend `tests/test_scaffold.py`'s `TestCiWorkflow` class with assertions naming both fixture invocations.
Not here:   no change to the two fixture files themselves; no change to `scripts/plan-lint`'s own behavior.

Done means:
1. [cap]  `.github/workflows/ci.yml`'s `lint` job runs `ruff check .`   (tier: test-backed `tests/test_scaffold.py`)
2. [cap]  the same job's `scripts/plan-lint` step exits 0 against `clean-plan.md`, exits 1 against `broken-plan.md`, and the job still reports success on that expected 1   (tier: test-backed `tests/test_scaffold.py`)
3. [hold] Task 1's `test` job definition is unaffected by this addition   (tier: script `.github/workflows/ci.yml`)
Evidence: (recorded by scripts/evidence-capture once /build executes this task; none yet -- this plan has not been built)

### Task 3 — Update `CLAUDE.md`'s Linter row to drop the "not yet wired into a CI job" caveat
Why now:    the caveat becomes false the moment Task 2's `lint` job is live; a stale caveat left in place is worse than none, and this repo's own "no fourth document class" stance means the doc that's now wrong gets fixed, not left be.
Read first: `CLAUDE.md`
Rests on:   Task 2 (the caveat is only false once the `lint` job actually runs `ruff check .` in CI).
Do:         edit `CLAUDE.md`'s "Linter -- Ruff..." row to remove "not yet wired into a CI job (tracked separately)" and name `.github/workflows/ci.yml`'s `lint` job as where it now runs.
Not here:   no other `CLAUDE.md` row changes; no rewording of the rule-set list itself.

Done means:
1. [cap]  `CLAUDE.md`'s Linter row no longer contains the string "not yet wired into a CI job", and instead names `.github/workflows/ci.yml`   (tier: test-backed `tests/test_scaffold.py`)
2. [hold] `CLAUDE.md`'s Tests row (baseline command) is unmodified by this task   (tier: script `CLAUDE.md`)
Evidence: (recorded by scripts/evidence-capture once /build executes this task; none yet -- this plan has not been built)

## Not-here follow-ups
- A release-blocking status-check requirement on the `main` branch ruleset so a red `test`/`lint` job actually blocks merge, not just reports -- a repo-settings change outside this diff.
- Linting a `/plan`-authored `PLAN.md` itself in CI, once a story routinely commits one as demonstration evidence -- deferred to a later story; the two static fixtures already give the `lint` job a stable, always-present target.
- A type-checking job -- `CLAUDE.md` names no type checker for this repo today, so there is nothing to wire yet.

## Revision History

### 2026-07-16 (round 1)
- Simulated collision fixture only, not a real sign-off.
