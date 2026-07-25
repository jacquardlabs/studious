# M5 (`/finish`) epic — required-demonstration coverage summary

Addresses the acceptance gate's fix-and-retry finding on
`epic/m5-finish-skill` at HEAD `c7e02ca`: acceptance criterion 7
("Demonstrated end-to-end against a real BUILT branch") was unmet — no
`docs/jig/evidence/<date>-<task>/` folder, no dated build report, and no
demonstration artifact anywhere on the branch or in its history.

Two real, non-scratch `/build` → `/finish` cycles were run end to end
against this repo, each fixing a genuinely filed, real bug (never a
fabricated task), exercising two of the four Step 6 verdict tokens with
git/GitHub state verified row-by-row per `skills/finish/SKILL.md`'s Step 6
table. A real bug in `scripts/status-flip` blocked the very first attempt
and was fixed (with a regression test) before either demonstration could
complete — itself evidence the "genuine, non-scratch" requirement caught a
real gap synthetic test fixtures had missed.

## Demonstration 1 — MERGE

Branch `build/ruff-extend-select-fix-202607122211` (base:
`epic/m5-finish-skill` at `c7e02ca`), fixing
[jacquardlabs/jig#36](https://github.com/jacquardlabs/jig/issues/36)
(`pyproject.toml`'s ruff config used `select`, silently disabling Pyflakes
and default pycodestyle checks). `/build` reached `BUILT` (3/3 Done-means
items PASS); `/finish` ran all six steps and reported `MERGE`.

- Evidence: `docs/jig/evidence/2026-07-12-task-1/` (this repo's *first
  ever* committed evidence folder, with a real `manifest.json`) — now on
  this branch via the merge commit `1a0485f`.
- Report: `docs/jig/reports/2026-07-12-ruff-extend-select-fix-build-report.md`
  — now on this branch.
- Filed follow-up: [jacquardlabs/jig#55](https://github.com/jacquardlabs/jig/issues/55)
  (accepted, per-item); a second draft was skipped, per-item, demonstrating
  the non-batch confirmation contract.
- Step 6, verified: worktree removed (`git worktree list` no longer shows
  it), branch deleted (`git branch --list` empty), no PR opened
  (`gh pr list` confirms none).

## Demonstration 2 — PR

Branch `build/design-md-vocab-fix-202607122225` (base: `main`), fixing
[jacquardlabs/jig#47](https://github.com/jacquardlabs/jig/issues/47)
(DESIGN.md's Vocabulary table miscategorized `FIX` as a fourth terminal
`/build` task status and omitted `RESAMPLE`). `/build` reached `BUILT`
(3/3 items PASS, after correcting one Foreman transcription bug in the
verify items file itself — no new executor dispatched, matching the
"Foreman's own bug, re-transcribe and retry" path); `/finish` ran all six
steps and reported `PR`.

- Evidence + report live on that branch (not merged into
  `epic/m5-finish-skill` — `PR` doesn't merge anything), each with the
  same committed-folder/real-manifest shape as Demonstration 1.
- Filed follow-up: [jacquardlabs/jig#56](https://github.com/jacquardlabs/jig/issues/56).
- Step 6, verified: worktree present (`git worktree list`), branch
  present and confirmed **not** merged into `main`, PR open —
  [jacquardlabs/jig#57](https://github.com/jacquardlabs/jig/pull/57)
  (`state: OPEN`), carrying the assembled evidence table + cctx note +
  filed-issue link + report link as its body.

## KEEP and DISCARD — reasoned, not separately run

Both demonstrations above already exercise every git primitive Step 6's
cleanup draws on: `git worktree remove`, `git branch -D`, `git merge
--no-ff`, `git push` + `gh pr create`, and — shared by every verdict,
run identically in both demonstrations above — the pre-cleanup commit
removing `PLAN.md` before any verdict-specific action.

- **KEEP** performs *only* that shared pre-cleanup commit, then stops —
  no further git action at all. Both demonstrations above performed that
  exact commit for real (`0af3aa8` and `afe95c5`); KEEP adds no new
  mechanism beyond declining to run the git actions MERGE and PR already
  ran successfully.
- **DISCARD** is mechanically MERGE's own cleanup (`git worktree remove`
  + `git branch -D`) with the `git merge` step omitted. Demonstration 1
  already ran both of those removal primitives successfully and they were
  verified above.

Every primitive either token would exercise has therefore already run for
real in this repo, not merely been asserted; treating KEEP/DISCARD as the
reasoned remainder (rather than two more full `/build` cycles solely to
re-exercise primitives already proven) is this fix's own judgment call,
consistent with the acceptance gate's own "ideally all four, or the
feasible subset with the rest reasoned" allowance.

## Cross-check against Step 6's table

| Verdict | Worktree | Branch | PR | Verified how |
|---|---|---|---|---|
| MERGE | Removed | Deleted | None | Demonstration 1, directly |
| PR | Kept | Kept, un-merged | Opened | Demonstration 2, directly |
| KEEP | Kept | Kept | None | Reasoned: shared pre-cleanup commit only, already run twice above |
| DISCARD | Removed | Deleted | None | Reasoned: same two primitives as MERGE's cleanup, already run and verified in Demonstration 1 |
