# Architecture review — 2026-07-17

Whole-codebase periodic review. Baseline (first run; the directory held only `.gitkeep`).

## Summary

Structurally healthy for its size and unusually disciplined: the scripts layer is a set of dependency-free standalone CLIs with git fully centralized in one shared module, no god objects, and complexity concentrated in the one place it belongs (the `/build` loop). The biggest concern is not a mess but a load-bearing gap — the verification backbone this product's entire thesis rests on ("scripts re-verify everything; nothing signs off on itself") is not enforced in CI: the only workflow runs semantic-release, so the 7,929-line test suite and Ruff never gate a merge. The biggest strength is the deliberate "N independent encodings + cross-surface pinning test" pattern that keeps prose, code, and docs from drifting — brilliant, well-documented, and also the codebase's main long-term maintenance liability as skill count grows.

## Dependency map

Three layers (the code is a two-layer plugin as documented, plus an unnamed third layer — see drift note):

- **Mechanics (scripts/, 2,554 LOC)** — Python CLIs, standard-library only. Two shared modules:
  - `scripts/_gitutil.py` — imported by 6 scripts (`evidence-capture`, `evidence-freshness`, `plan-lint`, `status-flip`, `verify`, `worktree-setup`). **Top load-bearing module.** All git access routes through its `run()`/`run_shell_with_timeout()` — no script shells out to git directly.
  - `scripts/_planparse.py` — imported by 2 (`plan-lint`, `verify`). Single home for `### Task N` block + `Done means` grammar.
  - `build-report` and `design-lint` are leaf CLIs (no shared-module imports).
- **Judgment (skills/, 1,790 LOC prose)** — six `SKILL.md` files. `skills/build/SKILL.md` (600 lines) is the orchestration hub; it invokes `verify` (6x), `status-flip` (5x), `plan-lint` (3x), `worktree-setup`/`evidence-capture` (2x each). `/plan` leans on `plan-lint` (8x). Prose is the runtime authority.
- **Verification (tests/, 7,929 LOC — larger than scripts + skills combined)** — `unittest`, plus six non-collected derivation helpers. Load-bearing test helpers by importer count: `_vocabulary` (7), `_frontmatter` (7), `_tempgit` (6), then `_orphancheck`/`_load_bearing` (2), `_task_split_boundary` (1).

**Transitively load-bearing documents:** `DESIGN.md` (parsed by `_vocabulary.py`, which 7 test files import) and the `SKILL.md` files (parsed by `_task_split_boundary.py`, `_load_bearing_cross_surface.py`) are runtime inputs to the test suite, not just human docs. A wording change cascades to test failures by design.

**Core-journey data flow** (clean throughout; PLAN.md is the shared state file, `docs/jig/evidence/*/{results,manifest}.json` the persistent artifact store):
`/design` → `design-lint` + `verify` + `evidence-capture`; `/plan` → `plan-lint`(`_planparse`) + `verify`; `/build` → `worktree-setup` → `verify`(`_planparse`+`_gitutil`) → `status-flip` → `evidence-capture`; `/finish` → `build-report` + `evidence-freshness`. The one convoluted spot is load-bearing derivation, which crosses three surfaces (below).

### Actual vs documented architecture style

CLAUDE.md/DESIGN.md describe a **two-layer plugin**: judgment in prose, mechanics in scripts. The mechanics layer matches the documentation faithfully — deterministic exit codes, standalone CLIs, centralized git, functional-core decomposition (`design-lint`'s `check_1..5`, `verify`'s item pipeline). **Drift:** the *test/derivation layer* is a de-facto third architectural layer the docs never name — the largest body of code in the repo, carrying the entire drift-prevention burden by parsing the docs and skills as structured input. The architecture is really three layers, not two, and the third is both undocumented and unenforced in CI.

## Findings

### Critical

None. No structural defect is actively causing bugs today; the closest concern is the CI gap below, held at Important because the maintainer's own `/build` loop runs `verify` locally.

### Important

**1 · No CI enforcement of tests or lint** · `.github/workflows/release.yml` (only workflow) · dimension: evolution-readiness / cross-cutting enforcement · The sole workflow runs `semantic-release` on push to `main` (post-merge); it invokes no `unittest`, no `pytest`, no `ruff`. The 7,929-line suite — including the cross-surface pinning tests that are the codebase's only defense against the triple-encoding drift below — never gates a PR. CLAUDE.md concedes the linter is "not yet wired into a CI job." For a product whose ratified principle is "nothing signs off on itself; scripts re-verify everything," the CI has no re-verification step. · confidence: **Confirmed** · recommendation: add a PR-triggered workflow running `uv run --no-project python3 -m unittest discover -s tests` and `ruff check`; make it required. This is prerequisite to trusting every Track finding's mitigation.

**2 · Divergent task-heading parsers across PLAN.md surfaces** · `scripts/_planparse.py:31` vs `tests/_load_bearing.py:24` · dimension: boundaries / data-flow · `_planparse` matches `^### Task (\d+)\b` (numeric labels only); the test-side reference `_load_bearing._task_blocks` matches `^### Task (\S+) — (.*)$` (any label, em-dash separator required). `_load_bearing_cross_surface.py` asserts the real `plan-lint.compute_load_bearing` and the reference `derive_load_bearing_set` agree — but only over fixtures both regexes parse identically. A real plan with a non-numeric label (`Task 1a`) or a missing em-dash would partition differently, and the "agreement" test would not catch it because such a plan is never fixtured. · confidence: **Confirmed** (both patterns read directly) · recommendation: have the reference impl consume `_planparse`'s shared `TASK_HEADING_RE`/`split_tasks`, or add fixtures at the label/separator boundary so the cross-surface test actually exercises the divergence.

### Track

**3 · Triple-encoding pattern is the defining architecture — document the tradeoff** · `scripts/plan-lint` + `tests/_load_bearing.py` + `skills/build/SKILL.md` step 1.5 (load-bearing); `_planparse` + `_task_split_boundary` + two SKILL prose rules (task-split); `_vocabulary.py` + `DESIGN.md` table + each `SKILL.md` (vocabulary) · dimension: complexity-distribution · Each rule is encoded up to 3x — SKILL.md prose (runtime authority), script code, and a test reference impl — bound by regex-over-prose derivations that raise `AssertionError` when the doc is reworded even if meaning is preserved. Deliberate, extensively documented in every helper's docstring, and genuinely elegant; also a maintenance surface that grows linearly with each new skill and rule. PRODUCT.md already names "fragile vocabulary derivation" as debt. Compounds with Finding 1: the pinning tests that justify the triplication don't run in CI. · confidence: **Confirmed** · recommendation: record this pattern explicitly in CLAUDE.md as an accepted tradeoff (it is currently only discoverable by reading `tests/_*.py` docstrings), and set a watch-item: revisit if a seventh skill pushes the derivation-helper count past a maintainability threshold.

**4 · Context docs are code-coupled runtime inputs** · `DESIGN.md`, `skills/*/SKILL.md` ← `tests/_vocabulary.py`, `tests/_task_split_boundary.py` · dimension: boundaries · `DESIGN.md`'s Vocabulary table and several `SKILL.md` prose phrasings are parsed as structured data by the test suite; they are load-bearing code inputs, not free prose. This is the intended single-source-of-truth mechanism, but it means "edit the doc" now carries test-breakage risk that a doc's appearance doesn't signal. · confidence: **Confirmed** · recommendation: accept and note in CLAUDE.md alongside Finding 3 so a future editor knows a table-cell rename is a code change; no structural rework needed.

## Recommended priority order

1. **Finding 1** — wire a required PR CI job (tests + Ruff). Everything else's mitigation is unverifiable until this lands; smallest effort, largest leverage.
2. **Finding 2** — unify the task-heading parser or fixture the boundary; a latent correctness gap on the load-bearing (literally) path, cheap once CI exists to prove the fix.
3. **Finding 3 & 4** — documentation-only: add the tradeoff notes to CLAUDE.md so the third architectural layer stops being tribal knowledge.

## Trend vs last cycle

Baseline — first architecture review for this project; no prior reports in `docs/studious/architecture-reviews/`. Every finding is new by definition.

## Residual line

Verified clean: git access is fully centralized in `_gitutil` (no script shells out to git directly — confirmed by grep); no god objects (`build-report` 85 LOC, largest script `design-lint` 561 LOC decomposes into `check_1..5`; the 600-line `build/SKILL.md` is core-loop prose, complexity correctly concentrated); no database, no migrations, no denormalized JSON blobs beyond the structured `manifest.json`/`results.json` artifact store (dataclass-serialized); no cross-cutting concern reimplemented per-module. Limitations: I did not execute the test suite or scripts (read-only posture), so cross-surface *agreement* is assessed from the fixture set and regexes as written, not from a run; import counts are static grep, not a runtime graph. One out-of-scope observation for the next product review: PRODUCT.md still lists bug #36 (Ruff `select` vs `extend-select`) as open, but `pyproject.toml:26` already uses `extend-select` — stale.
