# Pre-mortem — M4 closeout: rough-in inspector + audit follow-ups

- Epic: m4-closeout
- Stories: rough-in-inspector (#15), subprocess-trust-and-timeout (#48, #49),
  evidence-label-path-traversal (#51), safety-behavior-regression-tests (#50)
- Branch: epic/m4-closeout
- SHA: 73b2c81
- Date: 2026-07-15

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | product | `rough-in-inspector`'s design phase widens #15's three named jurisdictions (test self-dealing, contract match, technicality gaming) into general code review, duplicating `/gate-audit`'s own auditors instead of staying the narrow, load-bearing-only pass the issue scopes. | Read the design doc's jurisdiction section; confirm it cites only the issue's three bullets and adds no fourth lens. |
| 2 | technical | "Load-bearing" gets derived from a heuristic that only works for hand-authored quick-path plans (e.g. grepping `Rests on` text) since no `/plan`-produced spine map exists yet (M3 unbuilt) — and the design doesn't flag this as provisional, so it silently becomes the permanent definition once `/plan` ships a real spine map. | Confirm the design doc explicitly names its heuristic and marks it provisional pending M3, not presented as the final mechanism. |
| 3 | integration | `rough-in-inspector` and `safety-behavior-regression-tests` both edit `skills/build/SKILL.md` and `tests/test_build_skill.py`; run concurrently under the cap-2 schedule, whichever lands second risks a merge conflict the driver's one permitted merge-fix attempt can't cleanly reconcile. | Check `gate-ledger epic-get --slug m4-closeout` after the drive; a `parked` status with a merge-conflict reason on either story confirms this and needs a manual merge. |
| 4 | technical | `subprocess-trust-and-timeout` (docs the trust boundary in `worktree-setup` + `verify`) and `evidence-label-path-traversal` (hardens `evidence-capture`'s own input validation) land independently and leave inconsistent trust-boundary phrasing across the three command-adjacent scripts — two say one thing, the third says another or nothing. | After both land, grep `worktree-setup`, `verify`, `evidence-capture`, and `status-flip` for the trust-boundary docstring/comment and confirm consistent wording, not just presence in two of three. |
| 5 | process | #46 (`docs/design/build-skill.md` reconciliation) is stale — the file was already deleted by commit `e6fd44e` enforcing jig's own doc-lifecycle policy — but nothing in this epic's scope guards against some future story silently recreating it if a contributor doesn't check first. | Before any story in this epic (or a later one) touches `docs/design/`, confirm the directory still holds only `finish-skill.md` — any `build-skill.md` reappearing is the risk materializing. |
