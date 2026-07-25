# /finish — build/ruff-extend-select-fix-202607122211

Verdict: **MERGE** into `epic/m5-finish-skill`. No PR opened (see Step 6);
this report is the durable home for the assembled evidence table below,
per `docs/design/finish-skill.md`'s Open Questions note on where that
content lives when there's no PR body to hold it.

This branch fixes issue [#36](https://github.com/jacquardlabs/jig/issues/36)
(`pyproject.toml`'s `[tool.ruff.lint]` used `select`, silently disabling
Pyflakes and the default pycodestyle checks) and doubles as the M5
(`/finish`) epic's own required real `/build` demonstration
(`docs/design/finish-skill.md`, "Required demonstration"): a genuine,
non-scratch `docs/jig/evidence/2026-07-12-task-1/` folder with a real
`manifest.json`, freshness-held against its own recorded commit rather
than the branch's current `HEAD`.

## Step 1 — PR evidence table

Evidence folder: `docs/jig/evidence/2026-07-12-task-1/` (commit
`4cc30a495329dbdcc0ab46807ee982c27eaa2a67`). Freshness hold
(`scripts/evidence-freshness`): **PASS** — the folder's own manifest commit
is still an ancestor of this branch's current `HEAD` (`7320d56`, two
commits later: the evidence-capture commit and the status-flip commit),
and the captured artifact's mtime is still ≥ the manifest's
`commit_timestamp`. This is the freshness hold re-confirming against a
`HEAD` that has genuinely moved past the evidenced commit — the exact
scenario issue #44's bug shape would have broken, had the floor been
`HEAD` instead of the manifest.

| # | Done means item | Method | Evidence | Pass |
|---|---|---|---|---|
| 1 | `pyproject.toml`'s `[tool.ruff.lint]` declares `extend-select`, not `select` | script | see below | PASS |
| 2 | `ruff check .` exits 0 under the corrected config | script | see below | PASS |
| 3 | full test suite (`tests/`) still passes | test-backed | see below | PASS |

<details>
<summary>Item 1 — extend-select, not select (script)</summary>

```
command: grep -qE '^extend-select = \[' pyproject.toml && ! grep -qE '^select = \[' pyproject.toml
exit code: 0
```
</details>

<details>
<summary>Item 2 — ruff check . (script)</summary>

```
command: uv run --no-project --with ruff ruff check .
exit code: 0
--- stdout ---
All checks passed!
```
</details>

<details>
<summary>Item 3 — full test suite (test-backed)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -v
exit code: 0
--- stderr (unittest writes its summary to stderr) ---
...
----------------------------------------------------------------------
Ran 144 tests in 6.841s

OK (skipped=1)
```
</details>

No `Done means` item lacked an evidence folder; nothing is reported as
"evidence not found."

## Step 2 — cctx footer

cctx not installed; skipping the session-cost footer and harvest offer.
Install with `pipx install cctx-cli`. (This project's own current
environment — the path any real, non-scratch demonstration of this story
exercises first.)

## Step 3 — File survivors

`PLAN.md`'s `## Not-here follow-ups` section named 2 items. Both drafted
as GitHub issues and presented for **per-item** confirmation:

| Draft | Decision | Result |
|---|---|---|
| Wire `ruff check .` into a CI job | Accepted | Filed as jacquardlabs/jig#55 |
| Audit other Jacquard Labs repos for the same `select`/`extend-select` mistake | Skipped | Not actionable from jig's own tracker — belongs with whoever owns those repos, not filed here |

NOTES stubs: 0 found (`/build`'s current implementation does not yet write
these — an honest, not a broken, result per Step 3's own contract).

## Step 4 — Proposed decision patches (never applied)

One decision from this fix outlives the branch — a `CLAUDE.md` convention
worth keeping. Printed here only; **not applied** to `CLAUDE.md` by this
session, confirmed or not. The human copies this in by hand if they agree.

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@
 - **Linter** — Ruff. `pyproject.toml`'s `[tool.ruff.lint]` selects `B`, `C4`,
-  `PERF`, `PIE`, `RUF`, `SIM` (matches `reference/idioms/python.md`'s stated
-  rule set); not yet wired into a CI job (tracked separately).
+  `PERF`, `PIE`, `RUF`, `SIM`, via `extend-select` — never plain `select`,
+  which replaces ruff's own default rule set (E4/E7/E9/F, including
+  Pyflakes) instead of adding to it (issue #36). Not yet wired into a CI
+  job (tracked separately, issue #55).
```

## Step 5 — This report

Written by `scripts/build-report --repo <worktree> --slug
ruff-extend-select-fix --content <this file>` to
`docs/jig/reports/2026-07-12-ruff-extend-select-fix-build-report.md`,
committed as its own commit, distinct from Step 6's cleanup commit.

## Step 6 — Verdict + cleanup

**MERGE** into `epic/m5-finish-skill` — this branch's own base (the branch
this worktree was created from; `build/ruff-extend-select-fix-202607122211`
does not follow the `<parent>--<story-slug>` naming convention, so
resolution here is direct operator knowledge of how the worktree was
created, not an automated heuristic; see `docs/design/finish-skill.md`'s
Open Questions on base-branch resolution).

- Worktree: removed.
- Branch: deleted after a successful merge.
- PR: none opened.

Cleanup commit (removing `PLAN.md` — no `docs/design/<slug>.md` exists;
this was a quick-path plan) precedes the merge, per Step 6's shared
pre-cleanup contract. `docs/jig/evidence/` and `docs/jig/reports/` are not
touched by that cleanup — both are kept post-merge.
