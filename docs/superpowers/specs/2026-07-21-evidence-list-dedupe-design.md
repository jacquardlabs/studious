# `gate-ledger evidence-list --dedupe` — a collapsing read for long-running branches

**Date:** 2026-07-21
**Status:** Design, pre-implementation
**Source:** [#162](https://github.com/jacquardlabs/studious/issues/162), story
`evidence-list-dedupe` of epic `perf-audit-followups`

## Problem & persona

PRODUCT.md's secondary persona: **"The maintainer dogfooding Studious on Studious."**
This story changes no gate's judgment and no verdict a primary-persona developer sees —
`/gate-audit`'s test-auditor/premortem-auditor and `/gate-acceptance`'s premortem-auditor
still cite exactly the same kind of fact (has command X been run, and did it pass) they
cite today. Its beneficiary is whoever runs those gates repeatedly on one branch — the
primary persona iterating through fix/re-audit cycles, and the maintainer dogfooding a
multi-round epic story alike — and the job-to-be-done is named directly in the epic's
own goal: close "an unbounded evidence log" without touching any gate's judgment, only
its cost.

Issue #162, in its own words: `.studious/evidence/<branch-slug>.jsonl` is
"append-only with no cap: every verification command captured while a story is armed
adds one line, for the entire lifetime of the branch. A feature that goes through
several audit/acceptance fix cycles accumulates one entry per test/lint/build
invocation across every one of those cycles." PR #156 (`ee0d1aa`, this repo's own
immediately-prior commit — verified via `git log`, not assumed) already removed the
*per-dispatch repetition* cost: its own commit message states the diff/evidence-log
steps "now write to scratch files instead of the orchestrator retyping their content
into every dispatch prompt," and `commands/gate-audit.md`'s evidence step (lines
28-34) confirms this — the log is read once into a scratch file and referenced by
path across the test-auditor and premortem-auditor dispatches, instead of being
stamped verbatim into each. But the log's own *size* is untouched: a branch with a
long fix-cycle history still hands every one of those lanes the entire history as
input tokens on every gate run, most of which is superseded by later re-runs of the
same command.

Verified against the current files on this branch:

- `reference/evidence-format.md`'s own "Reading the log: `evidence-list`" section
  states the read verb "prints the file verbatim — nothing if it's absent" and its
  "Consumers that must stay in sync" list names exactly the three call sites this
  story's acceptance criteria name: `commands/gate-audit.md` (auditor 5/13 dispatches),
  `commands/gate-acceptance.md` (Part 2 premortem dispatch), and `commands/handback.md`
  (full manifest).
- `commands/gate-audit.md` lines 28-34 ("Resolve the branch's evidence log") capture
  `gate-ledger evidence-list` once into a scratch file (`$evidence_file`) and hand its
  path to auditor 5 (test-auditor) and auditor 13 (premortem-auditor, when a register
  exists), with an explicit textual fallback — "if that Read fails, fall back to
  running `gate-ledger evidence-list` yourself" — appearing in the same instruction
  block as the scratch-file path.
- `commands/gate-acceptance.md` lines 25-31 ("Resolve the branch's evidence log") run
  `gate-ledger evidence-list` once and stamp its output verbatim into only the Part 2
  premortem-auditor dispatch.
- `commands/handback.md` reads the log five separate times today (line 45 for the
  manifest table, line 127 for the per-row jq pipeline, and three further independent
  calls at lines 142, 143, and 144 for the total/passed/failed counts) — that
  redundant-read cost is a *different* epic finding (story
  `handback-single-evidence-read`, issue #161, running in parallel in this same epic)
  and is explicitly out of this story's scope; this story only adds the one-line note
  (§"The edit to `commands/handback.md`" below) confirming handback keeps reading the
  raw form, deliberately.
- `bin/gate-ledger`'s `cmd_evidence_list` (lines 774-792) is a byte-verbatim `cat` of
  the branch's `.jsonl` file today — no `jq` dependency at all on the read side. Its own
  comment states this explicitly: "Never requires jq: reading and emitting the raw file
  needs no JSON parsing."
- A **real, live evidence log already on this machine**
  (`.studious/evidence/worktree-cut-down-on-token-usage.jsonl`, from unrelated prior
  work in this same repo checkout) demonstrates the exact failure mode concretely: 64
  raw records, 61 distinct `command` values — one command
  (`uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v 2>&1`)
  appears 4 times. A collapsing read of that file returns 61 records, not 64 — verified
  directly with `jq` against the live file (below), not assumed.

Principle this leans on directly (CLAUDE.md): **"Code owns bookkeeping; prompts own
judgment."** Which record is the current, authoritative one for a given verification
command is a mechanical fact derivable from the log alone (its append order already
encodes recency) — not a judgment call an auditor should have to make by scanning
history and guessing which of several same-command entries is live. Today that
scanning is implicitly delegated to whichever auditor reads the raw log; this story
moves the mechanical part into `bin/gate-ledger`, the one place the log's storage and
read anchoring (`evidence_dir()`/`branch_slug()`) already live, exactly like the reuse
pattern the sibling `epic-reconcile-verb` story applies to `epic-get`/`work-get`/
`gate-get`.

## Proposed design

Add a boolean `--dedupe` flag to the existing `gate-ledger evidence-list` verb.
Composed with `--branch` exactly like today's flag (order-independent):

```
gate-ledger evidence-list [--branch B] [--dedupe]
```

**Semantics — "keep the most recent record per distinct command," stated precisely:**
from the full ordered list of records in the branch's `.jsonl`, retain exactly one
record for each distinct value of the `command` field — the one that was appended
*last* — and print exactly those retained records, in the same relative order they
already held in the file (i.e., still oldest-decision-first among the survivors,
since a survivor's position is always its own most-recent append). No record is
modified: a retained record is emitted byte-for-byte as it was appended, per
`reference/evidence-format.md`'s pinned shape — this flag changes which records are
selected, never how a selected record is shaped.

This is the literal reading of the acceptance criteria's own example ("keeping the
most recent record per distinct command"), and it is the one collapsing strategy that
cannot silently drop a still-live command's only record — see "Alternatives
considered" below for why a size- or count-bounded window (`--tail N`) does not have
that property.

### Implementation shape: one `jq` pipeline, gated behind a `have jq` check

`cmd_evidence_list` keeps its existing early return unchanged — `[ -f "$file" ] ||
return 0` still fires before any `--dedupe`/`jq` handling, so a branch with no
evidence log at all behaves identically whether or not `jq` is installed and whether
or not `--dedupe` was passed. Only when the file exists and `--dedupe` was requested
does the verb need `jq` — the plain (non-deduped) path stays exactly as
dependency-free as it is today.

Verified directly against the real log named above (not a synthetic fixture):

```bash
$ jq -s 'length' .studious/evidence/worktree-cut-down-on-token-usage.jsonl
64
$ jq -c -s 'to_entries as $es
  | (reduce $es[] as $e ({}; .[$e.value.command] = $e.key)) as $last_idx
  | $es[] | select(.key == $last_idx[.value.command]) | .value' \
  .studious/evidence/worktree-cut-down-on-token-usage.jsonl | wc -l
61
```

The pipeline: slurp the file into an array (`-s`), pair each record with its index
(`to_entries`), reduce over the array to build a `command → last index seen` map
(overwriting on every occurrence, so the map ends up holding each command's *final*
index), then filter the original indexed array down to only the entries whose index
matches that command's recorded last index. This is deliberately index-based rather
than value-based (e.g. `unique_by`/unique-then-compare-whole-object): `unique_by`
sorts by the grouping key and keeps one representative per group, which would
reorder the output alphabetically by command instead of preserving chronological
order among survivors — and a whole-object-equality approach (find the record equal
to the "latest" one for its command) is a latent bug for the edge case of two
records that happen to be byte-identical in every field, including `capturedAt` (a
command that legitimately runs twice within the same wall-clock second with the same
exit code) — such a pair would both satisfy an equality check and both survive,
silently violating "at most one record per distinct command." The index-based
`to_entries`/reduce form has no such collision: an index is unique by construction.

**Missing `jq`, or a malformed line in the file, when `--dedupe` is requested:** fail
closed — print nothing to stdout, one line to stderr (`gate-ledger: evidence-list
--dedupe requires jq` for the first case; a parse-failure message naming the file for
the second), non-zero exit. This introduces no new caller-side handling: both
`commands/gate-audit.md` and `commands/gate-acceptance.md` already document "If
`gate-ledger` is not found or `evidence-list` errors, treat it identically to empty
output and degrade silently" — a `--dedupe` failure is exactly that case, already
handled by prose written before this story existed. (A malformed line is not a new
risk class introduced by this flag, either — `commands/handback.md`'s existing jq
pipelines already parse every record per line today; `--dedupe` is simply the first
time `evidence-list` itself, rather than only its downstream readers, needs `jq` to
do that parsing.)

**No on-disk change of any kind.** `--dedupe` is a read-time transform only.
`cmd_evidence_append`'s append-only write path (`bin/gate-ledger` lines 724-772) is
untouched; the `.jsonl` file keeps growing exactly as it does today, indefinitely.
Whatever disk-space or long-term-storage concern "unbounded" might separately raise is
explicitly not this story's problem — see Out of scope.

### The three consumers this story updates

1. **`commands/gate-audit.md` line 30** — both occurrences of `gate-ledger
   evidence-list` in the "Resolve the branch's evidence log" step become `gate-ledger
   evidence-list --dedupe`: the precompute call that fills `$evidence_file`, *and* the
   prose fallback inside the same instruction block ("fall back to running `gate-ledger
   evidence-list` yourself") — both need the flag, or a `Read` failure on the scratch
   file would silently regress auditor 5/13 back to the full, undeduped log in exactly
   the case (a large log) this story exists to shrink.
2. **`commands/gate-acceptance.md` line 27** — its one `gate-ledger evidence-list` call
   becomes `gate-ledger evidence-list --dedupe`. Nothing else in that step's prose
   changes: "stamp it, verbatim, under an `Evidence log for this branch` heading" still
   describes exactly what happens to whatever `evidence-list --dedupe` returns.
3. **`commands/handback.md`** — no behavioral change (its five `evidence-list --branch`
   calls, lines 45/127/142/143/144, stay exactly as written; collapsing them into one
   read is story `handback-single-evidence-read`'s job, not this one's). This story adds one
   explicit sentence to step 2 ("Read the evidence log") stating the raw form is kept
   on purpose: a handback manifest's job is a complete historical record ("what was
   actually verified" across every fix cycle), not current-state-only — the opposite
   job `--dedupe` serves for an auditor citing a live claim. Recorded explicitly rather
   than left as silence, so a future edit doesn't "helpfully" switch handback to
   `--dedupe` too and quietly turn its manifest into a lossy summary.

Two docs outside the acceptance criteria's literal list still need updating to avoid
drift, since they are the files that already declare themselves the contract for this
verb:

4. **`reference/evidence-format.md`**'s "Reading the log: `evidence-list`" section gets
   a paragraph documenting `--dedupe` (semantics, the `jq` requirement, the fail-closed
   behavior) — this is the file that already states "Never requires jq" as a fact about
   the verb; leaving that sentence unqualified after this story ships would itself be
   the kind of silent doc/behavior drift this file exists to prevent. Its "Consumers
   that must stay in sync" list gains a line for the new fixture in
   `tests/test_gate_ledger.sh`.
5. **`bin/gate-ledger`'s own usage string** (the final `case` statement's `*)` arm) gets
   `evidence-list [--branch B] [--dedupe]` in place of `evidence-list [--branch B]`.

### Test fixture (acceptance criterion 3)

`tests/test_gate_ledger.sh` gains a new block, following the existing "evidence-list is
a plain passthrough" section's `sandbox()`/`evidence-append` idioms already in the file
(lines 585-609): append several records via repeated `evidence-append` calls where at
least one `--command` value repeats at least twice with a different `--exit-code` (so
its `predicate.result` visibly changes between the repeats, letting a test assert
*which* one survives, not just that collapsing happened), plus at least one command
that appears only once. Assertions, mirroring the file's existing `check`/`contains`
style:

- Raw `evidence-list` (no flag) line count equals the total number of `evidence-append`
  calls made — unchanged behavior, regression-proofing that adding `--dedupe` didn't
  touch the existing path.
- `evidence-list --dedupe` line count is strictly smaller than the raw count (the
  acceptance criterion's literal assertion), and specifically equal to the number of
  *distinct* commands appended.
- The deduped record for the repeated command has the **last**-appended exit code's
  `predicate.result`, not the first's — the test that actually exercises "most recent,"
  not just "fewer."
- The once-only command still appears exactly once in the deduped output — collapsing
  a repeated command must never drop an unrelated, non-repeated one.
- `evidence-list --dedupe --branch <other>` still resolves through the same anchoring
  `evidence-append` writes through (mirrors the existing "reads another branch's log
  without checking it out" and "from a linked worktree" coverage already in the file at
  lines 611-635) — one added case is enough; this story isn't re-proving anchoring from
  scratch, only that `--dedupe` doesn't bypass it.

Exact fixture command strings/exit codes and whether the loop building `stories`-style
coverage is written as several `evidence-append` calls or a pre-seeded file is cosmetic
and left to the build phase, as long as the five invariants above are what the new
block asserts.

## User journey

This extends PRODUCT.md's Journey 2 ("Per-feature gate flow") — specifically its
`/gate-audit` and `/gate-acceptance` legs — rather than adding a new journey; nothing
about when a gate runs or what a user does to invoke it changes.

**Before this story:** a feature goes through three audit rounds before it's clean —
say, `pytest tests/` fails, gets fixed, is re-run, passes; `npx eslint` is run twice for
the same reason. `/gate-audit`'s test-auditor and premortem-auditor (and
`/gate-acceptance`'s premortem-auditor) each receive all of those records — the two
stale `FAILED` entries alongside the two `PASSED` ones that superseded them — as input
tokens on every subsequent gate run for the rest of the branch's life, even the tenth
round.

**After this story:** the same two dispatches receive exactly the current state of
each distinct command — one entry for `pytest tests/` (the passing one), one for `npx
eslint` (the passing one) — regardless of how many rounds preceded it. The auditor's
own task is unchanged: "before writing a disclaimer that something can't be confirmed
without executing it, check the entries above for a command matching what you'd
otherwise flag... cite it exactly." That instruction was always implicitly asking for
the *current* state of a claim, never a historical narrative of every attempt — an
auditor citing a stale `FAILED` record over a later `PASSED` one for the same command
would already have been a mistake under today's raw log, just one the log's own
append-order left it exposed to making. Collapsing removes that exposure; it does not
remove any fact the auditor's task actually needed. `commands/handback.md`'s journey is
unchanged end to end — a handback reader still sees every attempt, in order, since that
manifest's whole job is the history a deduped read would throw away.

## Out of scope

- **Physically pruning, rotating, or truncating the on-disk `.jsonl` file.** The log
  keeps growing exactly as it does today; this story only shrinks what a *read* returns.
  Disk-space growth over a very long-lived branch, if it ever becomes its own problem,
  is a distinct future story (log rotation/archival), not this one — issue #162 itself
  frames the fix as "a mode that collapses the log before returning it," not a write-side
  change.
- **`commands/handback.md`'s own redundant-read cost** (reading the log five times per
  invocation) — that is story `handback-single-evidence-read` (issue #161), running in
  parallel in this same epic. This story's only edit to `handback.md` is the one-line
  note keeping it on the raw form deliberately.
- **A `--tail N` (most-recent-N-records) flag**, considered and rejected as the primary
  mechanism — see Alternatives.
- **Deduplicating on anything other than the literal `command` string** — e.g. two
  invocations of the same test file with different flags, or a fuzzy/semantic notion of
  "the same check," stay distinct records. This matches the acceptance criteria's own
  wording ("distinct command") and `reference/evidence-format.md`'s existing field
  description ("`command` ... verbatim").
- **Changing the record shape emitted for a surviving record** — every field a
  retained record carries is untouched; `--dedupe` selects which records pass through,
  never reshapes one. `outputDigest`, `predicate.configuration`, etc. remain exactly as
  `reference/evidence-format.md` pins them.
- **Any change to the "Evidence log for this branch" citation instructions** stamped
  into the test-auditor/premortem-auditor dispatch prompts — that guidance ("check the
  entries above for a command matching what you'd otherwise flag... cite it exactly")
  reads correctly against either the raw or the deduped form and needs no wording
  change; only the *source* of what gets stamped changes.
- **`bin/gate-ledger`'s narrowed-re-audit mechanism** (`.gates.audit.blockingLanes`) and
  the fix-delta cross-lane pass in `gate-audit.md` — an unrelated mechanism this story
  doesn't touch.

## Alternatives considered

- **`--tail N`** (keep only the most recent N records, regardless of command),
  the issue's own alternative suggestion. Rejected as the primary mechanism: an
  infrequently-run distinct command can fall entirely out of a fixed-size tail window
  once enough *other* commands are appended after it, silently hiding that command's
  only evidence from an auditor that would otherwise have cited it — a correctness
  regression `--dedupe` cannot produce, since every distinct command always keeps
  exactly one surviving record no matter how the log's overall size grows. `--tail N`
  remains a plausible *complementary* future addition for a branch with many genuinely
  distinct (not just repeated) commands, but the acceptance criteria ask for one
  collapsing mode, not two, and `--dedupe` alone directly serves the concrete failure
  issue #162 names (repeated re-runs of the *same* command across fix cycles).
- **Doing the collapsing in the orchestrating command doc** (stamping the `jq`
  dedup pipeline directly into `gate-audit.md`'s and `gate-acceptance.md`'s own Bash
  precompute steps) instead of adding a `gate-ledger` verb/flag. Rejected for the same
  reason `epic-reconcile-verb`'s design doc rejected the analogous choice for its own
  read composition: this is exactly the "schedulers... ledgers" bookkeeping CLAUDE.md
  assigns to code, not prose, and it would duplicate the same `jq` pipeline (and its
  edge-case reasoning) independently in two command docs instead of once in the one
  place `evidence_dir()`/`branch_slug()` anchoring already lives.
- **Shrinking the emitted record's shape** (e.g. dropping `outputDigest` from a
  deduped record to save more bytes) in addition to reducing record count. Rejected —
  scope creep past what the acceptance criteria ask for ("fewer records," not "smaller
  records"), and it would fork the record shape `reference/evidence-format.md` pins
  into a raw-shape and a deduped-shape, doubling what "Consumers that must stay in
  sync" has to track for no stated benefit.
- **Collapsing on write** (having `evidence-append` itself discard an existing record
  for the same command before appending the new one, so the on-disk file is always
  already deduped). Rejected — this would break `commands/handback.md`'s complete-history
  job outright (there would be no raw form left to read) and contradicts
  `cmd_evidence_append`'s own documented invariant ("append-only... never
  read-modify-write" — see that function's comment in `bin/gate-ledger`). A read-time
  flag is strictly additive and leaves every existing writer and every existing raw
  reader (`handback.md`, the "byte-for-byte" test at `tests/test_gate_ledger.sh` line
  607-609) completely unaffected.

## Success metrics

The observable signal: the record count (and proportional token count) of the evidence
block a test-auditor/premortem-auditor dispatch actually receives, on a branch that has
gone through more than one audit/acceptance fix cycle. Today that count grows by one
line per verification command run, per cycle, forever. After this story, for a branch
whose fix history re-runs a fixed set of C distinct verification commands across T total
invocations (T ≥ C, growing with every re-audit round), the deduped payload is exactly
C records — independent of T, the same "independent of N" shape
`epic-reconcile-verb`'s own success metric uses for its own round-trip count.

This story's own grounding data is a real measurement, not a synthetic one: the
`.studious/evidence/worktree-cut-down-on-token-usage.jsonl` file already present on
this machine (from unrelated prior work in this same repo checkout) has 64 raw
records and 61 distinct commands today — a real, live 3-record (4.7%) reduction,
verified directly with the exact `jq` pipeline above, not assumed. That log has not
yet been through many repeated fix cycles; the reduction scales with how many rounds a
branch actually goes through, which is the scenario issue #162 itself describes ("a
feature that goes through several audit/acceptance fix cycles").

Where it's read: directly, in `commands/gate-audit.md`'s own scratch file
(`$evidence_file`, whose byte size a maintainer can inspect with `wc -c` on any real
branch) and in any future gate-audit/gate-acceptance dispatch transcript — the
dispatched evidence block's record count should never exceed the branch's count of
distinct verification commands, regardless of how many audit/acceptance rounds
preceded that dispatch. Durably, `tests/test_gate_ledger.sh`'s new fixture (already
wired into CI per this repo's `ci.yml`) is the regression signal for the mechanism
itself.

## Operational readiness

**Migration:** none. No stored `.jsonl` shape changes, and no existing record's fields
change — `--dedupe` is purely an additive read-time filter over data that's already
there. Every branch's evidence log mid-flight right now (including this very epic's
five other stories) is read identically to today by anyone who doesn't pass the new
flag.

**Rollback:** revert the `cmd_evidence_list` diff in `bin/gate-ledger`, the usage-string
line, the two dispatch-prompt edits (`gate-audit.md`, `gate-acceptance.md`), the one-line
note in `handback.md`, the `reference/evidence-format.md` paragraph, and the new
`tests/test_gate_ledger.sh` block. Nothing on disk needs migrating back; every other
verb and every other caller of `evidence-list` (there are none besides the three named
here) is unaffected either way.

**Rollout:** normal merge-to-main via this story's own gate flow, then the epic's
finale. The very next `/gate-audit` or `/gate-acceptance` invocation on any branch,
including this one, picks up the collapsed dispatch automatically — no feature flag,
since both consuming command docs are edited directly rather than made conditional.

**Working/failing signal:** a broken `--dedupe` (malformed JSON output, wrong record
selected, a crash) fails synchronously and visibly to whichever caller parses it — the
`Read` of `$evidence_file` in `gate-audit.md`, or the stamped block in
`gate-acceptance.md`, would carry garbage or nothing rather than a plausible-looking
partial result, and `tests/test_gate_ledger.sh` (already in CI) is the durable
regression signal that catches a broken collapse before it ever reaches a real
dispatch — the closest thing this local CLI tool has to a production alarm, same as
the sibling `epic-reconcile-verb` story's own answer to this question.

## Open questions

- **Exact stderr wording for the two `--dedupe`-specific failure modes** (`jq` missing,
  a malformed line) is left to the build phase; the only load-bearing requirement is
  that both produce empty stdout and a non-zero exit, so the already-documented
  caller-side "treat identically to empty output, degrade silently" behavior in
  `gate-audit.md`/`gate-acceptance.md` applies without either file needing new
  handling.
- **Whether a future `--tail N` is ever added alongside `--dedupe`** (for a branch with
  many genuinely distinct, not just repeated, commands) is explicitly not decided here
  — flagged in Alternatives as a plausible complementary addition, not committed to or
  ruled out for later.
- **Exact fixture command strings, exit codes, and jq/loop construction inside the new
  `tests/test_gate_ledger.sh` block** are cosmetic, left to the build phase, as long as
  the five invariants listed under "Test fixture (acceptance criterion 3)" above are
  what it asserts.
