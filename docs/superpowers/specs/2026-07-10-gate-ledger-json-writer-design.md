# gate-ledger JSON writer — extract a shared `json_update` block

**Date:** 2026-07-10
**Status:** Design, pre-implementation
**Source:** [#102](https://github.com/jacquardlabs/studious/issues/102), story
`gate-ledger-json-writer` of epic `gate-ledger-robustness` (M2)

## Problem & persona

PRODUCT.md's secondary persona: **"The maintainer dogfooding Studious on Studious."**
This story has no effect any primary-persona developer using `/work-on` or
`/work-through` can observe — every verb's inputs, outputs, and exit codes stay
identical. Its beneficiary is the maintainer, and its job-to-be-done is named
directly in this epic's own goal: keep "the gate-ledger tooling itself
maintainable as it grows."

Issue #102, in its own words: `bin/gate-ledger` "crossed 500 lines (~550 now)…
driven by stamped boilerplate: the parse-args → jq/git guard → slugify →
mktemp/trap/jq/mv block repeats across six mutating verbs, and the jq csv
split/trim pipeline is stamped twice inside `cmd_epic_story_set`." The issue was
"deliberately deferred mid-branch" while `feat/work-through` was still landing
verb after verb, each copy-pasted from the last — exactly the condition under
which stamped boilerplate drifts: a fix to the write path (e.g. the crash-safety
fix that added the RETURN trap in the first place) has to be re-applied
identically five times, and nothing stops a sixth verb from being added later by
copying the block once more, mistakes and all.

Verified against the current file (`bin/gate-ledger`, 544 lines, this branch):
five verbs share the byte-for-byte block described above — `cmd_record`,
`cmd_work_set`, `cmd_work_log`, `cmd_epic_set`, `cmd_epic_story_set`. Issue #102's
"six mutating verbs" is the complement of the twelve total verbs against the six
that are pure reads (`status`, `gate-get`, `work-get`, `epic-get`, `epic-list`,
`work-list`): the sixth mutator is `cmd_gc`, which mutates a store by deleting
stale files outright (`rm -f`) rather than by producing new JSON through
`jq`+`mktemp`+`mv` — it has no `json_update` call site to convert, and its own
internal duplication (two near-identical prune loops, one per store) is a
different, smaller shape than the block this story targets. See Out of scope.

The epic's pre-mortem register (`docs/studious/premortems/gate-ledger-robustness-epic.md`,
failure mode 3) flagged a risk that scheduler-fixes and this story would both
rewrite `cmd_epic_story_set` (scheduler-fixes to namespace work-file slugs), and
recorded a DAG edge — this story depends on scheduler-fixes — so it wouldn't build
against pre-namespacing code. Verified directly against the merge commit
(`git diff f308963^1 f308963^2 -- bin/gate-ledger` is empty): scheduler-fixes
landed its namespacing convention entirely inside `workflows/epic-driver.js` and
never touched `bin/gate-ledger` (its own design doc's Alternatives Considered
section says why — building the qualified slug at the call site "sidesteps that
seam entirely"). The predicted collision didn't materialize; this design
proceeds against the current file exactly as it stands on this branch, five
matching blocks, no additional duplication left behind by scheduler-fixes to
absorb.

## Proposed design

- **A shared `json_update` writer replaces the five inline blocks.** Every
  mutating verb currently repeats: allocate a same-directory temp file, arm
  cleanup for that temp file, run `jq` with its own `--arg` list against the
  target file into the temp file, and rename the temp file over the target on
  success. `json_update` becomes the one place this sequence is written, taking
  the target file, the `jq` filter, and that verb's `--arg` pairs, and doing
  exactly what the inline block did — same temp-file location (so the final
  rename stays on one filesystem, same as today), same all-or-nothing outcome
  (the target file is either untouched or fully replaced with valid `jq`
  output, never partially written), same failure behavior (a failing filter
  leaves the target file untouched and a non-zero exit propagates to the verb's
  caller, exactly as today).
- **A constraint this consolidation must hold, not a detail it can leave to
  chance: exit-code propagation and crash-safe cleanup must be preserved
  exactly, including on the failure path.** This is the one place a mechanical
  extraction can silently stop being behavior-neutral. Verified directly (small
  reproduction scripts, not inference): today, each verb sets its own
  `RETURN` trap and its own temp-file cleanup runs exactly once, at that verb's
  own return, with the verb's real exit code intact. Once the mktemp/trap/jq/mv
  sequence moves into a separate function that a verb *calls* rather than
  *is*, a `RETURN` trap armed inside that new function does not stay scoped to
  it — bash re-fires it when the *calling* verb itself returns, and by then the
  temp-file variable that trap references has gone out of scope. Under this
  script's `set -u`, that is not a no-op: it is an "unbound variable" error
  that aborts the rest of the script, discarding the verb's real exit status
  even though the write itself had already succeeded. Any implementation of
  `json_update` must close this specific hole — the extraction is not
  behavior-neutral until a verb's caller sees the same exit code, on both the
  success and failure paths, that it sees today. (See Open questions for the
  mitigation choice, and for why the existing test suite's file-content
  assertions don't by themselves prove this constraint is met.)
- **The `--deps`/`--gates` csv split/trim pipeline in `cmd_epic_story_set` is
  defined once and used twice**, not stamped identically for each argument as
  it is today. Both fields go through the same `split on comma → trim
  whitespace off each element → drop empty elements` transform; today that
  three-step `jq` pipeline is written out in full for `deps` and again,
  verbatim, for `gates`. One definition, invoked for both arguments, removes
  the second copy without changing what either field ends up containing.
- **No verb's observable behavior changes.** Same flags accepted, same
  validation errors, same JSON shape written, same stdout/stderr, same exit
  codes for every case the current test suite exercises. This is a pure
  internal restructuring — CLAUDE.md's own framing for `bin/gate-ledger`
  applies directly here: "code owns bookkeeping," and this story is about
  keeping that code maintainable, not about changing what it keeps.

Principles this leans on (CLAUDE.md, PRODUCT.md):

- **Code owns bookkeeping; prompts own judgment** — this is bookkeeping-code
  hygiene work; no scheduling, verdict, or prompt logic is touched.
- **Minimize structural drift, prefer reuse over creation... prefer deletion
  over addition** (CLAUDE.md) — the story's whole shape is deleting duplicated
  blocks in favor of one shared one; it adds one small function and removes
  roughly as many lines as issue #102 estimates (~80).
- **Evidence over invention** — every claim above (five verbs not six, the
  scheduler-fixes non-collision, the trap-leak hazard) was checked against this
  branch's actual file and actual bash semantics, not assumed from the issue
  text or from other stories' design docs.

## User journey

This story sits below any journey PRODUCT.md names — it changes no command,
agent, or skill's behavior, and no critical user journey routes through it
differently before and after. The closest anchor is the maintainer persona's
implicit journey: read `bin/gate-ledger` to understand or extend it, change one
verb's write behavior, or add a new mutating verb. Before this story, that
maintainer edits (or copies) one of five near-identical 15-line blocks and must
remember to keep the other four in sync by hand if the write-path behavior
itself needs to change (as it did when the `RETURN`-trap crash-safety handling
was added — five separate edits, one per verb, all of which had to agree).
After this story, the maintainer calls `json_update` from a new verb the way
`work_file_init`/`epic_file_init` are already called today, and a fix to the
write path is one edit that every verb inherits.

## Out of scope

- **`cmd_gc`.** It mutates by deleting stale files directly (`rm -f`), never by
  producing new JSON through `jq`, so it has no block for `json_update` to
  replace. Its own duplication — two near-identical loops, one over the gates
  store and one over the work store, differing only in which directory and
  which log message — is a different, smaller pattern than the one this story
  targets and isn't named in the acceptance criteria. Worth a follow-up if the
  epic wants it, not folded in here.
- **Consolidating `ledger_dir`/`work_dir`/`epic_dir` into one parameterized
  `store_dir` helper.** Issue #102 cites "the store_dir consolidation from the
  same branch" as the *style* to follow for `json_update` (parameterize a
  repeated shape into one function), not as a second deliverable — and no such
  consolidation exists yet on this branch's `bin/gate-ledger` today (verified:
  the three `_dir` functions are still separate). Bundling it in here would
  widen a "behavior-neutral, mechanical" story into two independent refactors
  landing in one diff; if it's wanted, it's its own issue.
- **`scheduler-fixes`'s namespacing convention.** Confirmed not present in
  `bin/gate-ledger` (see Problem & persona) — nothing to reconcile or inherit.
- **Any change to what a verb accepts, validates, stores, or returns.** Every
  verb's argument parsing, validation error, and stored JSON shape stays
  exactly as it is; only the write mechanics move.
- **The store lock, worktree-anchoring, or any other correctness property of
  the surrounding stores** — unrelated to this refactor's mktemp/jq/mv target.

## Alternatives considered

- **Leave the duplication and accept the maintenance tax.** Rejected — this is
  precisely the "deliberately deferred" debt issue #102 exists to pay down, and
  the epic goal names "gate-ledger tooling itself stays maintainable as it
  grows" directly. The tax compounds with every new mutating verb.
- **Consolidate by having each verb build its own `jq` filter but share only
  the mktemp/trap/mv wrapper (a lower-level helper than `json_update`), leaving
  each verb to invoke `jq` itself.** Rejected — this still stamps the
  `mktemp`→`trap`→`jq`→`mv` *shape* five times even if some steps are shared,
  and it's the step ordering itself (temp file must exist before the trap
  fires, `jq`'s output must land before the `mv`) that's fragile to hand-copy;
  folding the `jq` invocation into the same helper as the temp-file and
  rename handling removes the one place order still matters from every call
  site.
- **Consolidate the three `_dir` functions and the `_file_init` functions too,
  in the same pass.** Rejected for this story — see Out of scope. The
  acceptance criteria scopes this to the mktemp/jq/mv block and the csv
  pipeline; widening it risks the "behavior-neutral, mechanical" property the
  100+-check test suite is meant to prove cheaply in one focused diff.

## Open questions

- **How `json_update` avoids the verified `RETURN`-trap leak (Problem &
  persona) is a build-phase choice, not mandated here.** Two mitigations were
  confirmed by direct reproduction to satisfy the constraint (verb's exit code
  and cleanup behavior unchanged on both success and failure): (a) a
  self-clearing trap — the trap body unsets itself (`trap - RETURN`) as its
  last action, so it cannot re-fire in the caller's frame — or (b) dropping the
  trap entirely in favor of an explicit success/failure branch inside
  `json_update` that removes the temp file and returns the real exit code on
  failure, never installing a trap that could leak in the first place. Both
  were verified, by isolated reproduction, to preserve exit-code propagation
  and leave no stray temp file on either path; either is acceptable. Whichever
  is chosen, the build phase should add one regression check that would have
  caught the leaked-trap failure mode if it existed: a mutating verb's `$?`
  immediately after a successful call is `0` (not corrupted by anything firing
  after the write completes).
- **The existing 109-check test suite does not, by itself, prove the exit-code
  constraint above.** It was run and confirmed green on this branch before
  this design was written. Its checks assert the written JSON's *content*
  (`jq -r '.gates.audit.verdict' "$f"`, etc.), not the CLI's exit status on the
  success path — only a few validation-error cases (`--concurrency banana`,
  a missing epic file) explicitly capture `rc=$?`. A version of `json_update`
  with the leaked-trap bug would still write correct JSON (the write happens
  before the trap fires) and would very likely pass all 109 checks unchanged
  while nonetheless exiting 1 with an "unbound variable" error on every single
  mutating call — a regression the acceptance criteria's "full existing test
  suite passes unchanged" would not, on its own, catch. The build phase should
  treat "the existing suite is green" as necessary but not sufficient, and
  either add the regression check named above or otherwise confirm success-path
  exit codes directly before calling this behavior-neutral.
- **Exact `json_update` signature** (argument order, how the containing
  directory is derived from the target file, whether `--arg` pairs are passed
  as trailing varargs or some other shape) is left to the build phase. All
  five call sites already agree that the temp file's directory is the target
  file's own containing directory, so no call site needs to pass that
  separately.
