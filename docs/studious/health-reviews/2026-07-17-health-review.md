# Codebase health review — 2026-07-17

Baseline run (first health review for this project; no prior reports to trend against).

## Summary

jig is a young, small, well-tested plugin repo (five shipped skills, ~8,100 lines of test code against ~2,300 lines of script code) with clean architecture — a thin CLI-script layer over two shared utility modules (`_gitutil.py`, `_planparse.py`), no circular imports, no god functions (largest function 104 lines). Biggest concern: the test suite is comprehensive but **never runs in CI** — the only GitHub workflow is `release.yml`; there's no test job, no lint job, and no branch protection on `main`, so nothing mechanical stops a regression from merging. Biggest strength: the context docs (PRODUCT.md's "Current known problems") are unusually honest about open issues, though one of those three (issue #36) turns out to already be fixed in code — a small but real drift between the tracker and reality.

## Critical (this week)

- **No CI test execution.** · `.github/workflows/` (only `release.yml`) · dependency/test-health · 28 test files (~8,100 lines) exist but nothing runs `unittest discover` on push/PR; `main` has no branch protection (`gh api .../branches/main/protection` → 404) · Confirmed · Add a `test.yml` workflow (`uv run --no-project python3 -m unittest discover -s tests -v`, matching CLAUDE.md's documented command) triggered on `pull_request`, and enable branch protection requiring it before merge.

## Important (this month)

- **Stale tracker entry: issue #36 already fixed in code.** · `pyproject.toml:16` vs `gh issue view 36` (OPEN) · technical-debt / drift · `pyproject.toml` already reads `extend-select = [...]` (fixed in commit `fc547f1`, M5); PRODUCT.md's "Current known problems" and the GitHub issue both still describe it as an open bug · Confirmed · Close issue #36 and refresh PRODUCT.md's known-problems list so it doesn't cite already-resolved work as outstanding.
- **`docs/design/*.md` accumulation is worse than when issue #71 was filed.** · `docs/design/` (7 tracked files: `design-lint.md`, `design-lint-reconcile.md`, `design-skill.md`, `finish-skill.md`, `plan-lint.md`, `plan-lint-ci.md`, `plan-skill.md`) · technical-debt / trend · issue #71's body cites 4 force-added files; 7 are tracked now despite the `.gitignore:17` rule matching all of them · Confirmed · Prioritize #71's ask #2 (mechanical safeguard — a lint check or epic-finale `git rm --cached` step) before the next milestone adds more.
- **No CI lint job either.** · `.github/workflows/release.yml` (only workflow) · technical-debt · Ruff is configured (`pyproject.toml`) but never invoked in CI; combined with the no-test-CI finding, PRs merge to `main` with zero automated quality gate · Confirmed · Same workflow addition as the Critical finding above should include a `ruff check .` step.
- **Shared utility module `_gitutil.py` has no direct unit test file.** · `scripts/_gitutil.py` (143 lines, imported by 6 of 7 CLI scripts, 4 touches in the last 90 days) · test-health · no `tests/test_gitutil.py`; its functions (`run_shell_with_timeout`, `resolve_revision_epoch`, `is_ancestor`, `branch_exists`, `worktree_registered`, etc.) are only exercised indirectly through each importing script's own test suite · Potential · Add a focused `test_gitutil.py` for the subprocess/timeout edge cases that six scripts otherwise each re-discover independently.

## Track (next review)

- **PRODUCT.md carries an unresolved editorial placeholder.** · `PRODUCT.md:49` (`<!-- FILL IN: ... -->`) · drift · the "Product principles" section still asks the maintainer to confirm the 5-of-11 selection; low urgency but it's a self-flagged incompleteness that's been sitting since the doc's last extraction pass · Confirmed · Resolve at the next `/deep-review product` pass, not urgent standalone.
- **Test-file size creeping toward the 500-line split bar.** · `tests/test_verify.py` (966 lines), `tests/test_design_lint.py` (740), `tests/test_build_skill.py` (696), `tests/test_plan_lint.py` (636) · technical-debt · four test files already exceed the god-file bar `code-auditor` applies to production code; none are unreasonable for the surface they cover today, but they're the largest and most likely to need splitting first · Potential · No action needed now; watch growth rate over the next 1-2 milestones.
- **`skills/build/SKILL.md` is both the largest skill doc and the most-churned file outside `.claude-plugin/plugin.json`.** · `skills/build/SKILL.md` (600 lines, 8 touches in the last 90 days) · architecture coherence · single file carries the fresh-executor loop, verification hookup, evidence-dir-commit step, and coach hand-off — no split needed yet, but it's the one file to watch for responsibility sprawl · Potential · If it crosses ~750 lines or gains another responsibility, that's the trigger for a `/deep-review architecture` pass.

## Metrics snapshot

- Test coverage: no coverage artifact exists and none was executed (read-only posture forbids running the suite) — could not verify
- TODO/FIXME count: 0 real debt markers in `skills/`/`scripts/` source (grep hits for "todo"/"workaround" were all literal status vocabulary, test names, or fixture content, not debt comments); 1 `FILL IN` placeholder in PRODUCT.md
- Outdated deps: N/A — no dependency manifest with third-party packages (`pyproject.toml` only configures `semantic-release`/`ruff` tool sections; no `requirements.txt`/`poetry.lock`/`uv.lock`); scripts and tests are stdlib-only
- Known vulnerabilities: N/A — same reason; no `pip-audit`/`osv-scanner` available in this environment either, so this lane is doubly unverifiable
- Largest file (lines): `tests/test_verify.py` at 966 lines (largest non-test source file: `scripts/design-lint` at 561 lines; largest skill doc: `skills/build/SKILL.md` at 600 lines)
- Coupling / circular-dependency count: 0 — clean one-direction imports from 7 CLI scripts into 2 shared modules (`_gitutil.py`, `_planparse.py`); no circularity found
- Dead-code symbol count: 0 confirmed — an initial grep-based sweep flagged ~50 "unused" functions, but spot-checks showed these were false positives caused by a `ugrep` shell alias mishandling extension-less script files; every sampled hit was actually imported and used (e.g. `_gitutil.git_repo_root` used by 4 scripts)
- Endpoint-convention-violation count: N/A — no API/endpoints; this is a CLI-script + Markdown-skill repo

## Trend vs last cycle

Baseline — no prior reports in `docs/studious/health-reviews/` (directory contained only `.gitkeep`).

## Residual

Verified clean: no circular imports, no functions over 200 lines (largest 104), no skip/xfail/flaky test markers (0 found), no copy-pasted *logic* clusters (the only repeated snippet was a 1-line `sys.path.insert` bootstrap shared by 6 scripts — trivial, not a real duplication risk). Lanes skipped: dependency-audit and known-vulnerability scanning (no third-party dependency manifest — stdlib-only repo) and API/endpoint conventions (no API surface). Assumptions: dead-code and coverage figures rely on manual grep/AST heuristics rather than `vulture`/`pyflakes`/`coverage.py` (none installed, and the read-only posture forbids installing or running them); treat the 0-dead-code and no-coverage-data figures as heuristic, not tool-verified. Test-suite content itself (pass/fail) was not executed per the read-only boundary.
