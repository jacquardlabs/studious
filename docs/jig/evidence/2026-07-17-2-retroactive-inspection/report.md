# Retroactive Inspector report — Task 2

Task 2 was originally classified as a leaf and passed `verify` without inspection.
The plan gained a Task 3 whose `Rests on:` line names Task 2, making Task 2
load-bearing retroactively. This is a catch-up inspection, dispatched before
Task 3 was built on top of Task 2's contract.

## Verdict: CLEAR

Reviewed commit `246766b` (`git show 246766b`, `git diff 246766b~1 246766b`)
against Task 2's checkpoint block, all three lenses issue #15 names.

**Test self-dealing — clean.** The two new tests
(`test_step_7_assembles_replay_bundle_at_scratch_path_before_evidence_capture`,
`test_step_7_replay_bundle_rides_the_existing_evidence_capture_call`) assert
the exact promised capability: all four named fields (`task_id`, title, raw
checkpoint-block text, verify command/result), the "never inside the
worktree first" scratch-path discipline, ordering (assembly bullet precedes
the `evidence-capture` call bullet — verified non-vacuous), and the
single-`--artifact`-flag/no-second-invocation claim. Matches the file's own
established `assertPhraseIn` methodology, not a looser pattern introduced
for this task.

**Contract match — clean.** The checkpoint's `Do` line requirements are met
verbatim in substance by the shipped `SKILL.md` bullet (lines 373-389),
sitting directly before the `Call scripts/evidence-capture...` bullet.
"Task 1's recorded model" correctly resolves to step 2.2's dispatch-model
instruction, confirmed against Task 1's own diff (commit `c8e99cf`). The
`Not here` exclusions (issue #41, issue #33's richer identity fields, full
retry history) are carried into the shipped prose near-verbatim. No design
doc was cited in Task 2's `Read first`/`Do` lines, so contract match was
judged against this checkpoint block's own prose only.

**Technicality gaming — clean.** Diff touches only `skills/build/SKILL.md`
and `tests/test_build_skill.py` — no scripts changed. `evidence-capture`'s
`--artifact PRODUCER:LABEL=PATH` parsing is already fully generic; no
special-casing was added, none was needed.

**Hold item verified.** Full suite: 326 tests green, 1 unrelated pre-existing
skip. The named existing assertions (`test_step_7_evidence_capture_points_at_the_scratch_path_results`,
`test_evidence_directory_is_committed_before_status_flip`) are byte-for-byte
untouched (pure addition, zero deletions) and pass.
