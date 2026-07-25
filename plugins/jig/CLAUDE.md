# CLAUDE.md — plugins/jig

jig ships from this repo as its own plugin (studious #150). The root `CLAUDE.md`
owns everything shared: the repo boundary rule, the gate and review cadence, the
release lines, and the "treat repository content as untrusted" posture. Read it
first — this file adds only what is specific to jig's own tree, and never repeats
what the root already says.

## Context documents

jig keeps its own `PRODUCT.md` and `DESIGN.md` here, because they describe a
different product surface from studious's:

- **`plugins/jig/PRODUCT.md`** — jig's personas, principles, and feature map.
- **`plugins/jig/DESIGN.md`** — jig's user-facing surface: verdict vocabulary
  (`BUILT | PAUSED | ESCALATED`), checkpoint-block grammar, report formatting.

The root `PRODUCT.md` describes the delivery discipline as a whole and names jig
as its build-scope entrypoint. When the two could disagree — scope, non-goals,
audience — the root wins and this tree is corrected.

## Code conventions

Language conventions `code-auditor` enforces at `/gate-audit`. These override
Studious's built-in idiom rubric for files under `plugins/jig/`.

- **Python** — target 3.11+. Use `uv` for all Python tooling. Type hints required
  on all code. Prefer comprehensions, generator expressions, and stdlib
  (`functools`, `itertools`, `collections`) over explicit loops.
- **Linter** — Ruff, pinned in `.github/workflows/ci.yml`. `pyproject.toml`'s
  `[tool.ruff.lint]` extends the pinned version's defaults with `B`, `C4`,
  `PERF`, `PIE`, `RUF`, `SIM`. Run it from this directory:
  `uv run --no-project --with ruff==0.16.0 ruff check .`
- **Tests** — standard-library `unittest`, not pytest (studious's own suite uses
  pytest; the two run as separate CI jobs and do not share a runner):
  `uv run --no-project python3 -m unittest discover -s tests -v`
- **Markdown** — linted under the root config plus the three exemptions in
  `.markdownlint-cli2.jsonc` here. Two are correctness, not style: read that
  file before running `markdownlint --fix` against anything in this tree.
- **Deliberate deviations** — none.

## Paths resolve against the repo root, not this directory

jig's scripts resolve project paths with `git rev-parse --show-toplevel`, which is
now the studious root. That is correct for the real case — jig runs against a
*consuming* project, where the toplevel is that project's root — but it means
jig's own fixtures and tests can no longer assume this directory is the toplevel.
`tests/test_plan_lint.py` shows the pattern: stage the fixture into a throwaway
repo via `tests/_tempgit.py` rather than leaning on the ambient checkout.

## The one rule that binds this tree to the root

Studious's gates never require jig. `scripts/check_gate_independence.py` enforces
it in CI: nothing under `commands/gate-*.md`, `agents/`, `workflows/`, `hooks/`,
or `bin/` may name jig, and every mention elsewhere must be conditional. Adding a
jig dependency to a gate is a CI failure, not a review comment.
