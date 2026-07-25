# Pre-mortem — M4 finale-audit follow-ups: verify + evidence-capture seams

- Epic: m4-verify-fixes
- Stories: probe-verify-freshness (#44), evidence-scratch-path (#45)
- Branch: epic/m4-verify-fixes
- SHA: ef95db6
- Date: 2026-07-12

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | Both stories edit the same `SKILL.md` step 2.5 line (`scripts/verify --items <file> --since <...> --out <results.json>`) — #44 changes the `--since` value, #45 adds scratch-path guidance around `--items`/`--out`. A mechanical merge-fix could keep one story's edit and silently drop the other's. | Diff the epic branch's `SKILL.md` step 2.5 against both story branches and confirm it carries BOTH fixes simultaneously — the corrected freshness floor AND the scratch-path instruction — not just one. |
| 2 | technical | #44's fix likely introduces a new freshness-floor concept (e.g. dispatch/task-start time) that `scripts/verify`'s existing tests don't cover. A fix that only makes the described symptom disappear, without a regression test for the case `--since` exists to prevent (a stale artifact copied forward from a prior attempt), could silently reopen the staleness gap `--since` was built to close (`build-scripts` premortem risk #5). | Confirm `tests/test_verify.py` gained a case for the corrected floor AND a still-must-fail case for a genuinely stale artifact — not just a happy-path assertion. |
| 3 | process | #45 is framed as a `SKILL.md` prose fix, but the actual defect is observable behavior in `evidence-capture`'s clean-tree enforcement. A words-only fix (updated instructions, unverified against a real run) wouldn't confirm the worktree actually stays clean on task 1. | Require demonstrated evidence — a real single-task run log — showing the worktree stayed clean and `evidence-capture` didn't refuse, not just an updated instruction paragraph. |
| 4 | integration | These two stories run with no dependency edge (concurrency cap 2) on the judgment call that the shared-line overlap isn't a real sequencing dependency. If the driver's one-permitted merge-fix attempt can't cleanly reconcile both edits, the second story to merge gets parked instead of landed. | Check `gate-ledger epic-get --slug m4-verify-fixes` after the drive; a `parked` status with a merge-conflict reason on either story confirms this risk materialized and needs a manual merge, not a blind retry. |
