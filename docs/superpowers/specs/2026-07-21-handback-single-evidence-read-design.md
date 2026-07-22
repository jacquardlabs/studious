# `handback.md` reads the evidence log once instead of four times

**Date:** 2026-07-21
**Status:** Design, pre-implementation
**Source:** [#161](https://github.com/jacquardlabs/studious/issues/161), story
`handback-single-evidence-read` of epic `perf-audit-followups`

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** `/handback` is that persona's own action, not a gate's —
`commands/handback.md` frames it as "the same commit authority a worker already
exercises for its own code," run by whoever just finished a phase (a dispatched
worker, or the persona themselves) to close it out before the next gate reads the
branch. The cost this story removes lands on exactly that moment: every `/handback`
invocation, on every branch, pays it.

### What issue #161 found

`commands/handback.md`'s step 4 ("A non-empty log — assemble the manifest") invokes
`gate-ledger evidence-list --branch "$branch"` **four separate times** to build one
report, verified directly against the file's current text:

- Once, piped through `jq`, to render the manifest table's rows.
- Once more for the total record count: `gate-ledger evidence-list --branch "$branch"
  | wc -l | tr -d ' '`.
- Once more for the passed count: `... | jq -r '.predicate.result' | grep -c
  '^PASSED$'`.
- Once more for the failed count: the same pattern against `'^FAILED$'`.

`bin/gate-ledger`'s own `cmd_evidence_list` (line 774's comment, verbatim: "print that
branch's evidence `.jsonl` verbatim") does no filtering or reshaping — it resolves the
branch's file through `evidence_dir()`/`branch_slug()` and emits it whole, every
line, every call. `reference/evidence-format.md`'s "Reading the log" section confirms
the same thing from the writer's side: this store is append-only and "only grows over
a branch's lifetime" (issue #161's own words, echoing the sibling `evidence-list-
dedupe` story in this same epic, filed for exactly that unbounded-growth problem).
Four calls means four full reads and four full re-emissions of the same file, on every
`/handback` run, and the cost scales with the file's size, not with anything about
what changed between calls — a `git log`-sized log costs the same as an empty one
would have, four times over instead of once.

**Bounding what this is not**, since the file carries a "bug" label alongside
"performance" on the tracker: this is not a correctness defect. The four calls all
read the identical, unmodified file — `/handback`'s own commands never write to the
evidence log (only `hooks/evidence-capture.sh` and `evidence-append` do that), and
`hooks/evidence-capture.sh`'s own `VERIFICATION_TOKENS` allow-list (checked directly
against every one of the four command strings above: `evidence-list`, `wc`, `tr`,
`jq`, `grep`, `PASSED`, `FAILED`) contains none of `pytest|jest|vitest|rspec|phpunit|
eslint|ruff|flake8|shellcheck|markdownlint|tsc|mypy|pyright|make|test|lint|typecheck|
check|build` as a word-boundary match, so none of `/handback`'s own read commands get
captured as new evidence mid-run. Four reads of a static file always produce four
identical outputs today. The fix is pure cost reduction, not a bug fix in the
behavioral sense — flagged here rather than left for a reader to wonder why "bug" and
"nothing was ever actually wrong" coexist.

## Proposed design

Capture the log once, into a shell variable, at the top of step 4 — the same step
that currently issues all four calls — and derive the manifest rows plus all three
counts from that one captured value. No new file, no new `gate-ledger` verb, no
change to step 2 (the emptiness check that gates entry into step 3 vs. step 4) or to
any other step.

**Principle this leans on:** PRODUCT.md's "Code owns bookkeeping; prompts own
judgment" — `cmd_evidence_list` in `bin/gate-ledger` already owns reading and
emitting the log; this design doesn't move that logic, duplicate it, or give the
prompt any new say over how the store is read. It only stops the prompt from asking
gate-ledger for the same answer four times when the prompt itself has nowhere else
to put the first answer but a variable. The read stays exactly one call into code;
the four derivations stay exactly where they already were, in the prompt's own
`jq`/`wc`/`grep` — this changes call count, not which layer owns which job.

### Before (current step 4, four reads)

```bash
gate-ledger evidence-list --branch "$branch" | jq -r '...'   # manifest rows
total=$(gate-ledger evidence-list --branch "$branch" | wc -l | tr -d ' ')
passed=$(gate-ledger evidence-list --branch "$branch" | jq -r '.predicate.result' | grep -c '^PASSED$' || true)
failed=$(gate-ledger evidence-list --branch "$branch" | jq -r '.predicate.result' | grep -c '^FAILED$' || true)
```

### After (one read, three derivations plus the rows)

```bash
evidence_log=$(gate-ledger evidence-list --branch "$branch")

total=$(printf '%s\n' "$evidence_log" | wc -l | tr -d ' ')
passed=$(printf '%s\n' "$evidence_log" | jq -r '.predicate.result' | grep -c '^PASSED$' || true)
failed=$(printf '%s\n' "$evidence_log" | jq -r '.predicate.result' | grep -c '^FAILED$' || true)

printf '%s\n' "$evidence_log" | jq -r '
  ((.outputDigest // "") as $d |
   [
     .capturedAt,
     ("`" + (.command | gsub("\\|"; "\\|")) + "`"),
     .predicate.result,
     .origin,
     (if $d == "" then "_(no digest captured)_" else $d end)
   ] | "| " + join(" | ") + " |")
'
```

`printf '%s\n' "$evidence_log"` reproduces the exact byte stream `jq`/`wc`/`grep` read
today: command substitution (`$(...)`) strips only the trailing newline(s) from the
captured output, never anything internal, and `printf '%s\n'` puts back exactly one —
the same shape the raw command's own stdout had. Nothing downstream of the capture
changes: the same `jq` filter, the same column order, the same `_(no digest
captured)_` placeholder rule, the same pass/fail token matching. A worker or gate
reading the rendered manifest afterward sees a byte-identical file to what today's
four-call version produces — this is an internal cost change, not a visible one.

**Why a variable, not a scratch file** (the issue's proposal names either): this
repo's own prompt-file convention already threads intermediate values through shell
variables at this exact call site — `slug=$(...)` in step 1, `total=$(...)`/
`passed=$(...)`/`failed=$(...)` already in step 4 today. Adding `evidence_log` as one
more variable of the same kind is the smaller diff and needs no new cleanup step (a
scratch file would need a path convention this command doesn't otherwise have, plus a
removal step so a stale file doesn't linger across an unrelated later run). The
JSONL content is bounded by ordinary shell command-substitution limits (no `ARG_MAX`
concern — this is captured output read on `stdin` by the downstream `jq`/`wc`/`grep`
calls, never re-passed as a command-line argument), so nothing about this design
depends on the log staying small; `evidence-list-dedupe` (issue #162, sibling story,
same epic) is the story that bounds the log's own growth, not this one.

**Scope boundary with `evidence-list-dedupe`:** that story's own acceptance criteria
(`gate-ledger epic-get --slug perf-audit-followups`, read directly) state its new
`--dedupe` collapsing mode is adopted by `gate-audit.md` and `gate-acceptance.md`,
while "`handback.md`'s manifest explicitly keeps the raw form." This design doesn't
add `--dedupe` or any other new flag to the single call it makes — it captures
exactly what `gate-ledger evidence-list --branch "$branch"` already returns today, so
it composes with `evidence-list-dedupe` landing before, after, or never, in either
order, without conflict.

## User journey

Extends PRODUCT.md's critical user journey #2 ("Per-feature gate flow") at the "build
with your own workflow" step, immediately before `/gate-audit` — `/handback` is the
worker's own close-out action at that seam, not a gate itself.

1. A worker (dispatched agent or the persona directly) finishes a phase and runs
   `/handback` to close it out, per `reference/worker-contract.md`'s "the work,
   committed... uncommitted work does not exist."
2. **Before this story:** step 4 quietly re-reads and re-emits the same append-only
   evidence file four times before writing `docs/studious/handback/<slug>.md`. On a
   branch with a long history of verification commands, the user waits through four
   full passes over a file that only ever grows, for one report.
3. **After this story:** step 4 reads the file once, holds it in `$evidence_log`, and
   derives all four things (rows, total, passed, failed) from that one held value.
   The manifest file written to disk is unchanged — same header line, same table,
   same summary prose expectations. The user sees no different output, only less
   waiting for it.
4. **Must not regress:** step 3's "no log, or an empty one" branch is untouched —
   still its own read in step 2, still the same two-message distinction (not armed vs.
   armed-but-empty). This story's diff starts and ends inside step 4.

## Out of scope

Cross-checked against PRODUCT.md's "What we're NOT building": none of that list
(being a methodology, a separate orchestration product, auto-applying changes,
replacing the issue tracker, a monetization layer, a hosted service/dashboard) bears
on a shell-call-count reduction inside one existing command's own step — nothing
there is adjacent enough to this story to need an explicit carve-out.

- **Step 2's separate read** (the emptiness check gating step 3 vs. step 4). Issue
  #161 and this story's acceptance criteria both scope the fix to "the manifest-
  assembly step" (step 4) specifically. Folding step 2's read into the same captured
  value would take total invocations from five down to one instead of two, but it
  reaches into step 3's not-armed/empty distinction for a saving issue #161 never
  asked for — left to Alternatives considered below rather than folded in silently.
- **`evidence-list-dedupe`'s `--dedupe` collapsing mode** (issue #162). Separate
  story, separate acceptance criteria, and that story's own criteria name `handback
  .md` as the file that deliberately keeps reading the raw (non-deduped) form — this
  design doesn't touch that choice.
- **A new `gate-ledger` read verb** that pre-aggregates total/passed/failed
  server-side. `bin/gate-ledger`'s dispatch table already gained one new verb this
  cycle (`epic-reconcile`, issue #160, landed) and `evidence-list-dedupe` (issue #162,
  pending) is about to add a flag to an existing one — a shell-level capture-and-reuse
  gets the same reduction without a third touch to that shared file this cycle.
- **Any change to `bin/gate-ledger`, `hooks/evidence-capture.sh`, or
  `reference/evidence-format.md`.** The fix is a pure prompt-text restructuring of
  `commands/handback.md` step 4; the reader (`cmd_evidence_list`), the writer
  (`evidence-append`/the hook), and the record shape are all untouched.
- **The epic's five other findings** (auditor-8's inline dispatch cost, `gate-audit
  .md`'s dual-audience doc cost, `work-through`'s per-story reconcile round-trips, the
  unbounded evidence log, `gate-acceptance`'s invisible dispatch retries) — separate
  stories, untouched here.

## Alternatives considered

- **Fold step 2's read into the same capture, taking the whole command from five
  invocations to one.** Rejected for this story specifically, not because it's a
  worse design in the abstract — reusing an already-captured value is exactly this
  story's own logic, one level up. It's deferred because step 2/3 carry a distinction
  this design doesn't need to touch to satisfy issue #161: "not armed" (no work file
  claims this branch) vs. "armed, but the log is missing or empty" are two different
  facts today, checked by two different means (`gate-ledger work-list`'s branch
  column for the first, the evidence-list read itself for the second) — reworking
  that check to share a value with step 4 changes step 3's own logic surface for a
  saving (five calls to two, versus five calls to one) that issue #161 didn't
  request and this story's acceptance criteria don't name. A narrower diff that
  matches exactly what was asked for is the safer choice; a follow-up issue can widen
  the scope deliberately if the two-call remainder (step 2 plus step 4's now-single
  call) is judged worth closing later.
- **A new `gate-ledger` verb returning pre-computed total/passed/failed alongside the
  raw rows in one JSON payload**, so `commands/handback.md` never has to derive counts
  itself at all. Rejected on the same "avoid a third touch to `bin/gate-ledger`'s
  shared dispatch table this cycle" grounds `acceptance-retry-visibility`'s sibling
  design doc used for its own analogous choice — `epic-reconcile-verb` (#160) already
  landed and `evidence-list-dedupe` (#162) is pending against that same file this
  cycle; a prose-level capture-and-reuse gets the identical user-visible result
  without adding a third.
- **Redirect to a scratch file instead of a shell variable**, as issue #161's own
  proposal names as an alternative. Rejected: no cleanup step exists in this command
  for a scratch file today, this call site already uses shell variables for smaller
  derived values (`slug`, `total`, `passed`, `failed`), and the JSONL content has no
  size constraint that would force a file (see Proposed design's `ARG_MAX` note) —
  a variable is the smaller, more consistent diff.
- **Leave it as four calls, documented as an accepted cost.** Rejected: the fix costs
  one prose edit confined to step 4, removes three-quarters of the reads on every
  `/handback` invocation on every branch this command is ever run against, and
  changes no observable output — there's no real trade-off on the other side of this
  one.

## Success metrics

No user-facing product surface beyond `/handback`'s own execution cost — the
observable signal is structural, per the design-doc contract's allowance for that
shape here:

- **Invocation count, read directly off the diff:** `commands/handback.md`'s step 4
  contains exactly one `gate-ledger evidence-list --branch` invocation after this
  change, down from four — this is what this story's acceptance criteria ask a
  reviewer to verify directly, since (per the criteria's own text) "this is a prompt
  file with no execution harness, not a runtime test."
- **Byte-identical output, read by inspection:** the rendered
  `docs/studious/handback/<slug>.md` (header line's record/passed/failed counts, and
  the manifest table) is unchanged in shape and content from what the four-call
  version produces against the same underlying evidence log — confirmed by comparing
  the `jq` filter and column list in Proposed design's "after" block against step 4's
  existing text verbatim, not by running it (no execution harness exists for this
  prompt file, per the same acceptance-criteria note above).

## Operational readiness

- **Migration:** none. `commands/handback.md` is a prompt file with no persisted
  state of its own; nothing on disk changes shape, no `.studious/` file gains or
  loses a field, and every existing `docs/studious/handback/<slug>.md` already on a
  branch stays valid untouched.
- **Rollback:** revert the `commands/handback.md` step-4 prose edit. Nothing to
  migrate back either direction — the change is confined to which shell commands the
  step's prose instructs a worker to run, not any data shape.
- **Rollout:** ships via the plugin's normal release cadence; the next `/handback`
  invocation on any branch reads the reduced-call form automatically, no flag.
- **Working/failing signal:** this is prose instructing a worker which shell commands
  to run, not a gate verdict — its only failure mode is a malformed capture (e.g. a
  typo in `$evidence_log`'s variable name) producing an empty or wrong manifest,
  which a human reading the committed `docs/studious/handback/<slug>.md` file (step 7
  already reports its path and counts back to the user) would notice immediately as
  an obviously-wrong count or missing rows — the same visibility step 7 already
  provides today, unchanged by this story. `npx markdownlint-cli2` and
  `uv run --no-project python scripts/check_references.py` still need to pass on the
  edited command file; no new cross-references are introduced for the latter to
  check.

## Open questions

- **Whether the step 2 + step 4 read (five calls total today) should later collapse
  to a single call for the whole command**, deferred to Alternatives considered above
  as a deliberate, separate follow-up rather than folded in here. Not blocking — the
  narrower fix fully satisfies issue #161 and this story's acceptance criteria on its
  own.
- **Whether `evidence-list-dedupe` (issue #162), once built, should ever apply to
  `handback.md`'s manifest** despite its own acceptance criteria currently naming the
  raw form as the intended, permanent choice for this file. That's that story's
  design-review call, not this one's — flagged here only because it's the one open
  seam between these two sibling stories in the same epic.
