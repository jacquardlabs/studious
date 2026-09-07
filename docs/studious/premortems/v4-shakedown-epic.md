# Epic pre-mortem — v4-shakedown

Branch: epic/v4-shakedown
Date: 2026-09-07

Cross-story failure modes for the v4 shakedown epic (#352, #351, #353), verified at
the epic finale by `agents/premortem-auditor.md`.

## 1. Shared-file edit collision

#352 and #353 both touch `commands/health.md` — #352 renames the master-summary
filename and adds a persona line elsewhere; #353 adds a gauntlet-absent stop line and
an untrusted-data note. Different line ranges, but if both are worked before merging
into the epic branch, expect a merge conflict on that file at merge time, not a design
conflict — reconcile by hand.

## 2. Self-modifying orchestrator

#353 edits `workflows/epic-driver.js`, the same script driving this epic. If #353
lands mid-run, later driver invocations for any still-in-flight story run against a
changed driver. Low risk since #351 (the canary) is expected to land first, but named
here so a mid-run behavior shift isn't mistaken for a new defect.

## 3. CI gap during the retro-stats test move

#351 deletes `tests/jig/test_retro_stats.py` and adds `tests/python/test_retro_stats.py`.
Doing this as two commits would open a window where neither file's tests run in CI —
the story's acceptance criteria already require the move to land atomically in one
commit.
