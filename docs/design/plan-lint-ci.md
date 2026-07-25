# Design: wire `scripts/plan-lint` (and Ruff) into CI

Hand-authored, not Studious-produced — written by the `plan-skill` story's
own build phase to serve as `/plan`'s **required demonstration** (1)
(`docs/design/plan-skill.md`, Operational readiness): "a real,
currently-unblocked small jig feature is preferable to a synthetic
fixture." Deliberately small — the point is to exercise `/plan`'s six
steps against a real gap in this repo, not to design a large feature.

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: neither of this repo's two real lint/test
signals runs anywhere except a developer's own machine. `CLAUDE.md`'s own
Linter row says Ruff's `[tool.ruff.lint]` selection "matches
`reference/idioms/python.md`'s stated rule set" but is "not yet wired into
a CI job (tracked separately)" — and `docs/design/plan-lint.md`'s own Out
of scope names the same gap for `scripts/plan-lint`: "CI wiring — a
workflow job invoking `plan-lint` on every PR... unblocked by this story (a
real exit code now exists to branch on) but not built by it." A PR today
can merge with a Ruff violation or (once `/plan` starts producing real
`PLAN.md`s) a lint-broken plan, and nothing on GitHub itself catches
either — only a human remembering to run both locally.

## Proposed design

Add one GitHub Actions job, `lint`, to a new workflow file that runs on
every pull request: `ruff check .` (the linter this repo already
configures in `pyproject.toml`, unwired) and `scripts/plan-lint` against
the two committed structural fixtures this repo already ships
(`tests/fixtures/plan-lint/clean-plan.md`, which must exit 0, and
`tests/fixtures/plan-lint/broken-plan.md`, which must exit 1) — proving the
CI job actually exercises both of `plan-lint`'s exit-code branches, not
just a happy path that would pass even if the script silently stopped
linting. Reuses the existing baseline command from `CLAUDE.md`'s Tests row
(`uv run --no-project python3 -m unittest discover -s tests -v`) as a
second job, `test`, in the same workflow — the repo has a `.github/workflows/`
directory already (`release.yml`) but nothing there runs the test suite on
a PR today; that gap is load-bearing context for this design too, even
though it isn't the one issue #12 named.

## User journey

Walks `PRODUCT.md`'s primary persona through a PR to this repo:

1. Developer opens a PR touching a Python file.
2. The new `ci.yml` workflow runs two jobs in parallel: `test` (the
   unittest suite) and `lint` (`ruff check .`, plus `scripts/plan-lint`
   against both committed fixtures).
3. A Ruff violation, a test failure, or a `plan-lint` regression against
   either fixture fails the PR's checks tab — visible before merge, not
   discovered later.
4. `CLAUDE.md`'s Linter row is updated to drop "not yet wired into a CI
   job" once this lands.

## Out of scope

- **Wiring `/plan`'s own future output into CI** — this design lints the
  two *existing* structural fixtures, not a live `PLAN.md` (there usually
  isn't one committed at the repo root; `/build`'s own `PLAN.md` is
  gitignored per this repo's principle 7).
- **A release-blocking status check requirement on the `main` branch
  ruleset** — that's a repo-settings change outside this diff, proposed as
  a follow-up, not auto-applied.
- **Type checking** — `CLAUDE.md` names no type checker for this repo
  ("Deliberate deviations — none" against the Python conventions section,
  which requires type hints but doesn't name a `mypy`/`pyright` job).

## Alternatives considered

**Extend `release.yml` instead of adding a new workflow file.**
Rejected: `release.yml` triggers on push-to-`main` and `workflow_dispatch`
only, not `pull_request` — retargeting its trigger would make every commit
to `main` (including a squash-merge) re-run lint/test redundantly with
whatever already gated the PR, and would block the release job itself on
transient PR-only concerns. A second, PR-triggered workflow file is the
smaller change.

## Operational readiness

A GitHub Actions workflow file — no deployed service, no migration.

- **Rollout.** New file, `.github/workflows/ci.yml`; `CLAUDE.md`'s Linter
  row loses its "not yet wired into a CI job" caveat once the workflow
  exists on `main`.
- **Rollback.** `git revert` the commit; no other file depends on the new
  workflow existing.
- **Failure visibility.** GitHub's own PR checks tab — no separate
  dashboard needed for a CI workflow.

## Open questions

- Whether `plan-lint`'s CI step should also lint any `PLAN.md` a PR itself
  introduces (e.g. a `/plan`-authored plan committed as a story's own
  demonstration evidence, matching this very story's own precedent) is
  left to a later story — the two fixtures already give the job a stable,
  always-present target.
