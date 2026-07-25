# Code idioms and quality review — 2026-07-17

Repo-wide sweep (not diff-scoped). Scope: `scripts/`, `tests/`, `pyproject.toml`. All docs/*.md, evidence/, and premortem files were read for injection attempts only, not audited as code.

## Linter

`uvx ruff check --select B,C4,PERF,PIE,RUF,SIM .` (the exact rule set `pyproject.toml`'s `[tool.ruff.lint] extend-select` documents): **All checks passed!** No B/C4/PERF/PIE/RUF/SIM findings anywhere in the tree.

## Findings

| Severity | Location | Dimension | Finding | Confidence | Recommendation |
|---|---|---|---|---|---|
| Low | scripts/design-lint (561 lines) | maintainability | Sole file over the 500-line god-file threshold, driven by 5 independent design-doc checks living in one module | Confirmed | Consider splitting one-check-per-module (`_check1.py` … `_check5.py`) if a 6th check is ever added; not urgent at current size/cohesion |
| Low | scripts/verify:342-366 (`run_items`) | complexity | 5 positional parameters, one over the >4 threshold | Confirmed | Bundle `(repo, timeout, since_ts, parallel)` into a small `RunConfig`/dataclass if another parameter is ever added; not worth the churn today |
| Low | scripts/verify:139, :223, :273; scripts/evidence-freshness:55 | type-safety | Return type is bare `dict` rather than a `TypedDict`/dataclass/Pydantic-shaped type, so callers get no field-level type checking on `data["items"]`, `data["task"]`, etc. | Confirmed | Low urgency — these are internal script-to-script JSON blobs, not a public API surface; a `TypedDict` would be a cheap upgrade if the schema grows another field |
| Low | scripts/status-flip, scripts/verify, scripts/evidence-capture, scripts/worktree-setup, scripts/plan-lint, scripts/evidence-freshness | maintainability | Identical one-line `sys.path.insert(0, str(Path(__file__).resolve().parent))` boilerplate repeated in 6 scripts to import sibling `_gitutil`/`_planparse` | Confirmed | Working as intended per `_gitutil.py`'s own docstring (each script must stay a standalone, dependency-free CLI); not a real duplication problem, noting only because it's the one repeated pattern in the tree |

That's the complete finding list — everything else inspected below came back clean.

## Verified clean

- **Type safety**: zero `typing.Any` usage in production code (3 grep hits are all in prose/comments — "Any identifier…", "Any heading…", "Any task whose status…", not the type). No `as unknown as X`-style unsafe casts (n/a in Python), no non-null-assertion overuse (n/a). Every `def` in `scripts/` carries an explicit return type, including `-> None` where appropriate.
- **Error handling**: every script follows one consistent convention — usage errors and precondition failures raise/return exit code 2, check/verification failures return exit code 1, success returns 0. Exceptions are caught narrowly and by name everywhere (`OSError`, `json.JSONDecodeError`, `subprocess.TimeoutExpired`, `ValueError`) — no bare `except:`, no swallowed exceptions, no silent `except Exception: pass`. `scripts/_gitutil.py`'s `run_shell_with_timeout` explicitly handles the child-process-group-orphan case on timeout (`os.killpg` + `process.wait()` before re-raising) rather than leaking a process — the one place error-path cleanup actually matters in this codebase, and it's handled.
- **Idiomatic style**: Ruff (B/C4/PERF/PIE/RUF/SIM, per `pyproject.toml`) fully clean. Manually reviewed the 16 `for`-loop sites in `scripts/design-lint` (the file with the most): all are either generator-expression internals (already idiomatic) or genuine multi-branch stateful accumulators (`split_bullets`, `split_paragraph_sentences`) that a comprehension can't express — correctly left as loops, matching CLAUDE.md's "prefer comprehensions… over explicit loops" as a preference, not an absolute.
- **Hygiene**: `TODO`/`FIXME`/`XXX` count is 1, and that hit is a fixture string inside a test (`tests/test_plan_lint.py:556`, literal text being tested for, not a real TODO) — effectively 0 real TODOs, nowhere near the 20-item threshold. No commented-out code blocks found. No `print()` calls are stray debug output — every hit is a CLI's own stdout/stderr result reporting (its actual user-facing surface per DESIGN.md), consistent across all 8 scripts.
- **Consistency**: no pytest imports or fixtures anywhere — `tests/` is unittest-only via `unittest.TestCase` subclasses, matching CLAUDE.md's documented "no pytest dependency" convention exactly. No mixed async/sync patterns (codebase is fully synchronous, `ThreadPoolExecutor` used only for the one documented `verify --parallel` case). `# noqa` usage (10 hits, all `E402`) is consistently the same justified pattern — module-level `sys.path.insert` before a sibling import — with an inline comment explaining it each time.
- **Injection defense**: scanned every file in scope for text aimed at steering this review (e.g. "reviewed and approved", "skip this", "ignore previous") — no hits.

Assumptions: treated `scripts/*` shebang-executable files as Python per `file(1)`'s own identification and CLAUDE.md's stated fact (all of `pyproject.toml`, `scripts/*`, `tests/*.py` are Python). Did not execute `unittest discover` or any script (read-only posture) — cyclomatic-complexity figures above are from manual line-count/branch inspection, not a computed metric, since no complexity linter is wired in (matches CLAUDE.md: Ruff's rule set doesn't include `C901`, and that's a documented, not a missing, choice).

**Verdict: Clean.** Four Low-severity polish items, zero Critical/High/Medium findings; Ruff (the project's own documented linter and rule set) reports no violations anywhere in the tree.

## Metrics

- `any_count`: 0
- `console_log_count`: 56 (all CLI stdout/stderr result output across 8 scripts — the product's documented UX surface, not debug logging)
- `todo_count`: 1 (a test fixture literal, not a real outstanding TODO)
- `largest_file`: scripts/design-lint (561 lines)
- `longest_function`: scripts/verify `main()`, ~55 lines (lines 435-489)
