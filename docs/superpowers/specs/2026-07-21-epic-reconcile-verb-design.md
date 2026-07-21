# `gate-ledger epic-reconcile` — one composite read for work-through's reconcile step

**Date:** 2026-07-21
**Status:** Design, pre-implementation
**Source:** [#160](https://github.com/jacquardlabs/studious/issues/160), story
`epic-reconcile-verb` of epic `perf-audit-followups`

## Problem & persona

PRODUCT.md's secondary persona: **"The maintainer dogfooding Studious on Studious."**
This story changes no gate's judgment and no verdict a primary-persona developer sees —
`/work-through`'s reconcile step still resolves the exact same facts it resolves today,
from the exact same three stores. Its beneficiary is whoever runs `/work-through` on a
multi-story epic (primary persona and the maintainer alike — `/work-through` is one of
this plugin's own entrypoints, not a maintainer-only tool), and the job-to-be-done is
named directly in the epic's own goal: close "work-through's per-story reconcile
round-trips" without touching any gate's judgment, only its cost.

Issue #160, in its own words: `commands/work-through.md`'s "1 · Reconcile — evidence
first" step, run at the top of *every* driver invocation, resolves each unfinished
story's next phase via several sequential reads per story — `gate-ledger epic-get`
once, then per story `gate-ledger work-get`, `gate-ledger gate-get`, a design-doc
existence check, and (when a story claims `landed`) a `git log --oneline` check against
the epic worktree. "For a 5-story epic this is on the order of 15-20 sequential shell
round-trips — all before a single agent is dispatched — repeated on *every* invocation
of `/work-through` (a user re-running it to check progress, or resuming after any
pause, re-pays this in full)."

Verified against the current files on this branch:

- `commands/work-through.md`'s "1 · Reconcile" section (lines 91-110) names exactly the
  four per-story reads issue #160 describes, plus the one epic-level `epic-get`.
- `bin/gate-ledger` (810 lines, this branch) has twelve verbs; the three read verbs this
  story composes — `cmd_epic_get`, `cmd_work_get`, `cmd_gate_get` — each already do
  nothing but resolve a path and `cat` the file (or print nothing if absent). None
  mutate, none need `ensure_gitignore`. `epic-reconcile` joins them as a fourth pure
  read, not a mutator.
- `workflows/epic-driver.js` never re-reconciles: it trusts `args.epic`/`args.phases`
  verbatim as inputs (its own header comment: "assembled and reconciled by
  `commands/work-through.md` before invocation"). Reconciliation is entirely a
  prose-and-shell concern today, run once per invocation before the script — or the
  fallback driver — ever starts. That is exactly where this verb inserts itself.
- `gate-ledger epic-list` (run against this repo's live `.studious/epics/`) shows
  `perf-audit-followups running 0/6` right now — this very epic, in flight, containing
  this very story. The next real `/work-through` invocation against it, once this story
  lands, is this issue's own predicted saving measured for real, not a synthetic
  benchmark.

Principle this leans on directly (CLAUDE.md): **"Code owns bookkeeping; prompts own
judgment."** Reconciliation — gathering recorded facts from three stores and one git
check — carries no judgment; today it is nonetheless expressed as a sequence of
separate CLI invocations a prompt has to enumerate and re-derive per story, once per
invocation, forever. Every additional story in an epic scales the cost linearly for no
new judgment gained.

## Proposed design

A new read verb, `gate-ledger epic-reconcile --slug <epic-slug>`, returns one JSON
object with everything `commands/work-through.md`'s reconcile step reads today:

```json
{
  "epic": { "...": "verbatim output of epic-get --slug <epic-slug>" },
  "stories": {
    "<story-slug>": {
      "work": { "...": "verbatim output of work-get --slug <epic-slug>--<story-slug>, or null" },
      "gate": { "...": "verbatim output of gate-get --branch epic/<epic-slug>--<story-slug>, or null" },
      "storyBranchHeadSha": "<short sha, or empty string if the branch doesn't exist yet>",
      "designDocExists": true,
      "landedButUnmerged": false
    }
  }
}
```

- **`stories` is keyed by the bare story slug** — the same keys already used inside
  `epic.stories` — not the epic-qualified `<epic>--<story>` form `work-get`/`gate-get`
  take as input. A caller already holding this payload never needs to re-derive that
  qualified string to look anything up.
- **`.epic` is byte-identical to a bare `epic-get --slug <epic-slug>` call.** Nothing
  inside it is added, removed, or reshaped. This is a deliberate constraint, not an
  incidental one: `commands/work-through.md`'s "2 · Run the driver script" step already
  hands `"epic": "<the epic-get JSON, verbatim>"` to the Workflow script — after this
  change that line reads `.epic` out of the reconcile payload instead of making a
  second call, and the script's own contract (`args.epic`) needs zero changes.
- **`work` and `gate` are `null` when the underlying file doesn't exist** (a story that
  hasn't reached `design` yet has no work file; a story that hasn't run a gate yet has
  no ledger file) — mirroring `work-get`/`gate-get`'s own "print nothing when absent"
  behavior, made explicit as JSON `null` instead of an empty string so a caller
  composing one object doesn't need special-case handling for "key missing" versus
  "key present but empty."

### Implementation shape: compose the existing read verbs, don't re-derive their paths

`cmd_epic_reconcile` calls `cmd_epic_get`, `cmd_work_get`, and `cmd_gate_get` directly
as bash functions already in this file — the same reuse pattern `json_update` set for
mutators, applied here to reads. Concretely, per story slug `s` pulled from
`epic_json | jq -r '.stories | keys[]'`:

```bash
work_json=$(cmd_work_get --slug "$slug--$s")     # raw, unslugified — cmd_work_get slugifies internally
gate_json=$(cmd_gate_get --branch "epic/$slug--$s")
```

This is not just economy of code — it's correctness reuse. `cmd_work_get`'s own
`--slug` argument is expected raw (unslugified) exactly as `workflows/epic-driver.js`'s
`workSlug(story)` already passes it (`${slug}--${story}`, no pre-slugify); `cmd_work_get`
slugifies internally, collapsing the `--` the same way `cmd_work_set` did when the file
was written. Re-deriving that path by hand inside the new verb (independently
slugifying, independently deciding whether `--` collapses before or after) is exactly
the kind of hand-copied logic CLAUDE.md's "prefer reuse over creation" warns against —
calling the existing function guarantees the read agrees with however the write side
already stores it, including if that collapsing rule ever changes. Same reasoning for
`cmd_gate_get --branch`: `branch_slug()` only maps `/` → `-` and does not collapse `--`,
so the gate-ledger filename this produces (`epic-<slug>--<story>.json`) is exactly the
file `record` already wrote when a gate ran from inside that story's worktree — reusing
`cmd_gate_get` means this verb never has to know that distinction exists.

### Two derived checks, not just three raw reads

The acceptance criteria's remaining two items — design-doc existence and the
landed/merged check — are facts this verb computes, not files it echoes:

**`designDocExists`** — `null` when `work.designDoc` isn't recorded (nothing to check);
otherwise a direct filesystem check for `<base>/<work.designDoc>`, where `<base>` is:

- `.studious/worktrees/<epic-slug>/__epic` if the story's recorded `status` is
  `landed` — its own worktree was removed by the merge dispatch
  (`workflows/epic-driver.js`'s merge round: `git worktree remove
  ".studious/worktrees/<slug>/<story>"` right after a successful merge), so the design
  doc that traveled with the merge now lives only in the epic worktree.
- `.studious/worktrees/<epic-slug>/<story-slug>` otherwise — the story's own worktree,
  which exists for exactly as long as the story is unlanded (`workflows/epic-driver.js`:
  `storyWorktree(story) = ${worktreesDir}/${story}`, `worktreesDir =
  ${repoRoot}/.studious/worktrees/${slug}`; deterministic, not read from any recorded
  `.worktree` field — verified no caller currently invokes `epic-story-set --worktree`
  with a real value, so nothing recorded there can be trusted as the source of truth).

**`landedButUnmerged`** — `false` unless the story's recorded `status` is `landed`, in
which case it's the negation of:

```bash
git merge-base --is-ancestor "refs/heads/epic/$slug--$s" "refs/heads/epic/$slug" 2>/dev/null
```

Verified directly (sandbox reproduction, not inference — three cases): a story branch
actually merged with `git merge --no-ff` into the epic branch returns exit `0` (is an
ancestor); a story branch that was never merged returns exit `1`; a story branch that
doesn't exist at all (ref unresolvable) fails with exit `128`. All three non-zero cases
collapse correctly to "not verified merged" through the same `2>/dev/null` + non-zero
check — no separate branch-existence check is needed first. This is the same technique
`workflows/epic-driver.js` already uses for its own narrower re-audit-scope check (`git
merge-base --is-ancestor "<sha>" HEAD`), reused here rather than invented — and it is
strictly more precise than the current prose's `git log --oneline` scan: it needs no
merge-commit message to mention the story's name, survives regardless of how the merge
was made, and needs no worktree checked out at all (refs are shared across worktrees of
one repo, so this runs correctly from wherever `gate-ledger` is invoked — the main
tree, another story's worktree, anywhere — not only from inside `__epic`).

### The edit to `commands/work-through.md`

"1 · Reconcile — evidence first" becomes one call:

```bash
gate-ledger epic-reconcile --slug "<slug>"
```

replacing its four bulleted per-story reads. The prose keeps doing exactly what it does
today with the result — deriving each unfinished story's next phase, flagging a
`landed` story whose `landedButUnmerged` came back `true` instead of silently trusting
it, correcting the ledger via `gate-ledger` (never by hand) when recorded state and
evidence disagree — it just reads all of that from one payload instead of reassembling
it from N+1 separate calls. "2 · Run the driver script" changes only its `args.epic`
line, from a second `epic-get` call to `.epic` pulled out of the same payload.

Principles this leans on (CLAUDE.md, PRODUCT.md):

- **Code owns bookkeeping; prompts own judgment** — this verb only aggregates recorded
  facts and computes two mechanical checks; it does not decide a story's next phase,
  does not correct a mismatch it finds, and does not touch `epic-story-set`. Judgment
  and correction both stay exactly where they are today: the calling prose.
- **Minimize structural drift, prefer reuse over creation** — one new verb, additive;
  every existing verb's signature, stored-file shape, and standalone behavior is
  unchanged. `epic-get`/`work-get`/`gate-get` still work exactly as before for any other
  caller (`epic-list`, ad hoc inspection, a future tool).
- **Evidence over invention** — every claim above (the current reconcile step's exact
  reads, the worktree-removal-on-merge timing, the three merge-base exit codes, the
  absence of any real `--worktree` writer) was checked against this branch's actual
  files and actual git behavior, not assumed from the issue text.

## User journey

PRODUCT.md's Critical user journeys section doesn't yet name an epic-driving journey
distinctly from Journey 2 ("Per-feature gate flow") — `/work-through` was built after
that extraction pass. CLAUDE.md is explicit that this isn't an oversight to route
around: "story (`/work-on`), epic (`/work-through`)... are entrypoints of one
discipline," the same journey run at a different altitude. This doc treats
`/work-through`'s reconcile-then-dispatch loop as Journey 2 run at epic altitude,
rather than inventing a new PRODUCT.md journey unilaterally — Studious's own principle
is "propose, don't apply" to context docs; a design doc for one story isn't the place
to add one.

**Before this story:** a user runs `/work-through` on a 5-story epic to check progress
or resume after a pause. Before a single agent is dispatched, the command works through
~17-21 sequential `gate-ledger`/`git` calls: one `epic-get`, then for each of the five
stories a `work-get`, a `gate-get`, a design-doc file check, and (for any story already
recorded `landed`) a `git log --oneline` scan of the epic worktree. Every one of those
is a full round-trip the orchestrating context pays for and waits on, and it repeats,
in full, on every single invocation — including a user just asking "where are we,"
which is exactly the resume-after-a-pause case the issue calls out.

**After this story:** the same check is one call — `gate-ledger epic-reconcile --slug
perf-audit-followups` — returning the epic's state, all five stories' work-file state,
all five stories' gate verdicts, all five design-doc existence checks, and all five
landed/merged checks in one JSON payload. The prose's own next step — deriving each
story's next phase and flagging any `landed`-but-unmerged story — is unchanged; only
the number of round-trips it takes to gather the facts that step reasons over drops
from ~17-21 to 1, independent of story count. Nothing about *when* a story is judged
ready to merge, *what* counts as evidence, or *how* a mismatch gets corrected changes —
this is the reconcile step's cost, not its verdicts.

## Out of scope

- **Deriving each story's next phase.** That judgment — "first phase in the gate
  profile whose evidence is missing," the `merge` sentinel when only the merge itself
  is outstanding — stays exactly where it is today, in `commands/work-through.md`'s
  prose, now reading its inputs from this verb's payload instead of N separate calls.
  Folding phase derivation into `bin/gate-ledger` would cross from bookkeeping into
  interpreting a gate profile against evidence — judgment the acceptance criteria's
  five-item list doesn't ask this verb to take on.
- **Correcting a `landed`-but-unmerged mismatch.** The verb reports
  `landedButUnmerged: true`; it does not itself call `epic-story-set` to fix the
  recorded status. "Evidence wins, and the files get corrected... when they disagree"
  stays the calling prose's job, exactly as today — this verb only makes the disagreement
  visible instead of requiring a `git log` scan to notice it.
- **Any change to `epic-get`, `work-get`, or `gate-get`'s own standalone signature,
  arguments, or output shape.** Every existing caller of those three verbs (`epic-list`,
  ad hoc inspection, a future tool) sees identical behavior; `epic-reconcile` is a new,
  additive verb built on top of them, not a replacement for calling them directly when
  only one piece is needed.
- **`workflows/epic-driver.js`'s own scheduling, merge, or finale logic.** The script
  already treats `args.epic`/`args.phases` as pre-reconciled inputs and needs no change
  beyond receiving the same `.epic` shape it receives today, sourced from one call
  instead of two.
- **Parallelizing the per-story sub-reads inside the new verb.** They stay sequential,
  in-process bash function calls — `cat`+`jq` against local files is already cheap; the
  cost this story removes is round-trips from the *orchestrating agent's* perspective
  (separate tool-call turns), not local disk I/O latency.
- **The `git merge --no-ff` mechanics, story-worktree creation/removal timing, or the
  epic finale flow.** Untouched; this verb only reads their aftermath.

## Alternatives considered

- **Teach the orchestrating prose to batch existing per-story calls into fewer shell
  invocations** (e.g., one Bash tool call chaining `work-get`/`gate-get` for every story
  with `&&`), without adding a new verb. Rejected — the orchestrating agent would still
  need a first round-trip just to learn the story slugs from `epic-get` before it could
  build that batch, and the result is N separate un-composited JSON blobs concatenated
  as text that the *prompt* then has to parse and correlate by story — moving
  composition work from code into a prompt, backwards from "code owns bookkeeping."
- **Compute `landedButUnmerged` and `designDocExists` inside `workflows/epic-driver.js`
  (JS) instead of `bin/gate-ledger`, since the script already does a merge-base check
  elsewhere (line 184) and already knows story-worktree paths.** Rejected — the
  reconcile step that needs these two facts runs in `commands/work-through.md`'s prose
  *before* the Workflow script is ever invoked (it's an input to `args.phases`, not
  something the script derives for itself), and the fallback (no-Workflow-tool) driver
  path has no JS to lean on at all. A bash verb in `gate-ledger` is the one
  implementation both paths already share; duplicating the check in JS as well would
  reintroduce the exact kind of duplication this epic's goal (and issue #102's
  `json_update` precedent) exists to close.
- **Have the new verb also decide and return each story's next phase**, absorbing the
  prose's remaining derivation step. Rejected — the acceptance criteria's five-item
  list stops at raw, recorded-or-computed facts; deciding a phase from a gate profile
  and those facts is judgment CLAUDE.md reserves for the prompt/script layer, not the
  ledger tool. Widening scope here isn't licensed by the story, and it would make this
  verb the second place (after the Workflow script) that has to know how to read a
  gate profile.

## Success metrics

The observable signal: the number of distinct tool round-trips (`gate-ledger`/`git`
invocations) `/work-through`'s reconcile step performs, per invocation. Today that
count scales with story count — roughly `1 + 4N` for an N-story epic (~17-21 for the
5-story epic issue #160 measured, and this epic's own 6 stories today). After this
change it is exactly `1`, independent of N.

Where it's read: directly, in `commands/work-through.md`'s own "1 · Reconcile" prose —
it should name exactly one `gate-ledger` invocation, no per-story loop language, no
separate `git log` step. Empirically, in any future `/work-through` session transcript,
the Reconcile step should show exactly one Bash tool-use block regardless of how many
stories the epic has. This epic is its own first real measurement: `perf-audit-followups`
is recorded `running`, `0/6` landed, right now (`gate-ledger epic-list`) — the next
`/work-through` invocation against it after this story lands is the saving issue #160
predicted, measured on a live epic rather than a synthetic one.

## Operational readiness

**Migration:** none. This verb is purely additive — no existing stored JSON shape
(`epic`, `work`, or `gate` files) changes; it only reads them. **Rollback:** revert the
two commits (the new `cmd_epic_reconcile` function + `case` arm in `bin/gate-ledger`;
the "1 · Reconcile" edit in `commands/work-through.md`). Nothing on disk needs
migrating back — every epic mid-flight on the old prose (including this repo's own five
other `running`/`ready` epics) is unaffected either way, since no other verb's schema
changes.

**Rollout:** normal merge-to-main via this story's own gate flow, then the epic's
finale; the very next `/work-through` invocation on any epic — this one included —
picks up the new reconcile step automatically. No feature flag or staged rollout: every
other additive verb this tool has gained (`--blocking-lanes`, `evidence-append`) shipped
the same way, since old callers of the verbs being composed here are entirely unaffected.

**Working/failing signal:** a broken `epic-reconcile` fails synchronously and visibly —
the very Bash call that replaced the sequential reads returns a non-zero exit or
malformed JSON directly to the orchestrating agent parsing it, with nothing async to
monitor. `tests/test_gate_ledger.sh` (already wired into CI per this repo's `ci.yml`) is
the durable regression signal: any future change to `bin/gate-ledger` that breaks this
verb's contract fails CI before merge — the closest thing this local CLI tool has to a
production alarm.

## Open questions

- **Error propagation when a per-story sub-read hits a corrupted stored file** is left
  to the build phase, mirroring the `json_update` precedent's own open question about
  exit-code propagation through a shared helper. `cmd_epic_get`/`cmd_work_get`/
  `cmd_gate_get` each just `cat` whatever bytes are on disk — a corrupted file doesn't
  fail the read itself, it fails the *next* `jq` parse of that output, deep inside
  `epic-reconcile`'s per-story loop. Under `set -uo pipefail`, a failed command
  substitution doesn't automatically abort the function unless its result is checked —
  so the build phase needs an explicit choice: fail the whole `epic-reconcile` call
  non-zero with a clear stderr message naming which store and which story (fail
  closed — a caller trusting one composite payload shouldn't have to guess which
  story's `null`/`false` means "legitimately absent" versus "read failed silently"), or
  some other explicit, tested behavior. Either way, this should ship with a regression
  check a hand-corrupted stored file exercises directly, the same way the build phase
  for `json_update` was asked to add one for its own leaked-trap failure mode.
- **Exact loop construction** (building the `stories` object story-by-story with
  repeated `jq` merges, versus one `jq -n` invocation fed by pre-built parallel
  arguments) is cosmetic and left to the build phase, as long as the output shape
  above is what ships.
- **`designDocExists`'s epic-worktree fallback for a `landed` story assumes the epic
  worktree still exists.** During normal mid-epic reconcile this always holds — only
  the whole-epic finale removes `__epic` (`workflows/epic-driver.js`'s ready-transition:
  `git worktree remove "${epicWorktree}"`), and a finale only runs once every story is
  already `landed`/`dropped`, at which point reconcile has no unfinished story left to
  ask this question about. The build phase should still degrade gracefully
  (`designDocExists: null`, not a crash) rather than assume this can never happen, in
  case `epic-reconcile` is ever invoked against an already-`ready` epic.
