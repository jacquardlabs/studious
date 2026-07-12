# Design: `handback` skill — evidence manifest + context capsule

**Date:** 2026-07-10
**Status:** Design, pre-implementation
**Story:** handback-skill (epic: worker-evidence-and-board)
**Source:** [#97](https://github.com/jacquardlabs/studious/issues/97)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The job-to-be-done sits at the exact seam PRODUCT.md
names for the worker layer: **"the *how* is no longer deferred to a companion
product: it enters through `reference/worker-contract.md` (story brief in;
implementation + evidence out), which any executor can satisfy — a dispatched agent, a
human, or Superpowers where installed."** `evidence-capture-hook` (landed, this epic)
made the "evidence out" half real by writing one record per verification command to
`.studious/evidence/<branch-slug>.jsonl` — but that log is gitignored, per-line JSON,
and local to whichever machine ran the commands. Nothing yet turns it into something a
human — reviewing a PR, or resuming a story after a break — can read in one place, and
nothing commits it to the branch, so it doesn't survive past the local checkout the way
the code itself does.

`reference/worker-contract.md`'s "What a worker must return" table already requires
**"A summary — what changed and why... Evidence — commands actually run with their
captured output... 'Done' without artifacts is not done."** Today that return is prose
in a chat transcript: read once by whoever dispatched the worker, then gone. The job
this story does: give a worker (dispatched agent, human, or a design-phase worker like
the one authoring this doc) a single, explicit action — "hand back" — that turns the
harness-captured evidence log plus the worker's own narrative into one committed
artifact on the branch, so the next reader (a human, a later phase's worker, or —
later, not this story — the board) doesn't have to reconstruct "what happened here"
from git log and a vanished transcript.

**Scope note on PRODUCT.md's own parked item.** PRODUCT.md's "What we're NOT building"
lists: *"A worker-layer skill set (evidence capture and handback first) is parked and
enters through the normal gates on its own evidence, not by default."* Like
`evidence-capture-hook` before it, this story is that re-entry, running under the same
approved epic plan and the same epic pre-mortem
(`docs/studious/premortems/worker-evidence-and-board-epic.md`) recorded at plan
approval — no separate `/gate-should-we-build` run is owed here, per
`reference/epic-plan-contract.md`'s batched-decision rule cited in the sibling design
doc. PRODUCT.md itself will need a proposed edit once the epic lands, moving this line
out of "What we're NOT building" — flagged here, not applied.

**Issue #97's own framing, verbatim:** *"`handback` skill — assembles the evidence
manifest + a provisional context capsule (summary + evidence; winnow Phase 3
formalizes the capsule schema later — do not wait for it) and commits them on the
story branch."* This design treats that sentence as the spec, not a paraphrase target.

## Proposed design

A new slash command, `/handback [branch]`, and a natural-language trigger skill,
`skills/handback/SKILL.md`, that shims to it — the same shape every other skill in
this repo already has (`skills/continue-feature-work` → `/work-on`,
`skills/check-studious-health` → `/studious-doctor`): a tightly-scoped `description`,
a body that delegates rather than reimplements.

**What `/handback` does, on the branch it targets (current branch if no argument):**

1. Read `.studious/evidence/<branch-slug>.jsonl` for that branch, per
   `reference/evidence-format.md`'s pinned shape.
2. **No log, or an empty one** → report that plainly (e.g. *"No evidence log found for
   `<branch>` — no verification commands were captured on this branch."*) and stop.
   Nothing is written, nothing is committed. This is the literal reading of the
   acceptance criteria's *"reports that instead of fabricating one"* — the no-log case
   produces a spoken/returned statement, not a stub file that just says "nothing here"
   committed to the branch for its own sake.
3. **A non-empty log** → assemble one markdown file,
   `docs/studious/handback/<branch-slug>.md`, with two sections:
   - **Evidence manifest** — every record in the log, one row per command: timestamp,
     command, result (`PASSED`/`FAILED` from `predicate.result`), origin
     (`interactive`/`subagent`), and the `outputDigest` — never raw stdout/stderr. The
     digest exists specifically so a log can be inspected without re-exposing whatever
     a failed command's output might have echoed (a token, a stack trace); the manifest
     must not defeat that by pasting raw output back in.
   - **Summary** — prose written by whoever is running the handback (the worker, or the
     human), grounded in real artifacts already on the branch: `git log` since the
     branch point, the design doc if one exists, and the evidence entries themselves.
     Not invented from nothing — PRODUCT.md's own principle, **"Evidence over
     invention"** ("extraction documents 'what IS'... never idealizes"), governs the
     summary the same way it governs context-doc extraction.
4. `git add` + `git commit` that one file, on the current branch, the same commit
   authority a worker already exercises for its own code (`reference/worker-contract.md`:
   *"The work, committed... Uncommitted work does not exist"*) — not a new authority
   Studious is granting itself. See "Why this isn't a `propose, don't apply` violation"
   below.
5. Report back: the file path and a one-line summary of what was captured (record
   count, PASSED/FAILED split), or the no-log message from step 2.

**Re-running `/handback` on the same branch** overwrites and recommits
`docs/studious/handback/<branch-slug>.md` rather than accumulating a new file per
invocation — the log only grows monotonically (append-only), so a later handback's
manifest is always a superset of an earlier one on the same branch, and git's own
commit history already preserves each prior snapshot. One current file per branch, not
a pile of dated ones, keeps `docs/studious/handback/` from filling with
near-duplicates the way a `deep-review`-style dated report would.

**Reading the log without duplicating gate-ledger's anchoring logic.** `bin/gate-ledger`
anchors all four of its stores (`gates/`, `work/`, `epics/`, and now `evidence/`) to the
*main* working tree root via `repo_root()`/`evidence_dir()` — deliberately, so a story
worker running in a linked worktree still lands (and finds) records in the one shared
`.studious/`. `reference/evidence-format.md` already names this story as one of the two
candidates that gets to shape the missing read verb: *"A gate-ledger read/query verb
for the evidence log... Deferred to whichever of `gates-cite-evidence` or
`handback-skill` first needs to read the log."* This story needs it first. `gate-ledger`
gains one minimal read verb, `evidence-list [--branch B]`, mirroring `work-list`'s
shape: it resolves the branch's evidence-log path through the same `evidence_dir()`
function `evidence-append` already uses and prints its contents (nothing if the file is
absent), so `/handback` never re-derives repo-root anchoring itself — reuse over
creation, one place each store's location logic lives.

**Why this isn't a "propose, don't apply" violation.** CLAUDE.md's recommend-only
invariant governs *review and gate* commands: *"Commands report; they never modify
external state... The sole exception: gate commands record verdicts, and `/work-on`
records flow position, to local, gitignored `.studious/` state."* `/handback` is
neither a gate nor a review — it emits no verdict, no PASS/FAIL, and isn't listed in
`reference/gate-vocabulary.md` (deliberately: it has no vocabulary to add). It's a
worker action, scoped by `reference/worker-contract.md`, which already assumes workers
commit their own output. The one genuine departure from precedent: every other
committed doc in `docs/studious/` (premortems, periodic reviews) is authored by a
*review* agent proposing content a human reads and, for context-doc edits, approves
before it lands elsewhere — `/handback`'s file is committed directly, by the worker,
the same way the worker's own code changes are. This is exactly the kind of judgment
call `/gate-design-review`'s Q2 (principle alignment) exists to weigh — flagged here
explicitly rather than asserted as obviously fine.

## User journey

Touches PRODUCT.md's critical journey #2, **per-feature gate flow** — specifically the
"build with your own workflow" step, now with an explicit closing action instead of an
implicit one.

Before this story: a worker finishes building (or finishes a design doc, or any other
phase), runs its own verification commands, and returns a prose summary + evidence
section per `reference/worker-contract.md`. That return lives in the dispatching
session's transcript only. A human resuming the branch later, or reviewing the PR,
reconstructs "what actually got checked here" from the transcript (if they have it), the
diff, or nothing.

After this story:

1. A story branch exists and is armed (`evidence-capture-hook`'s precondition — a work
   file whose `.branch` matches). The worker does its build (or design, or any other
   phase's) work; verification commands it runs get silently captured, exactly as
   `evidence-capture-hook` already does today — no change to that behavior.
2. Before returning control — to the driver, to a gate, or simply ending the session —
   the worker (or a human, on any branch) invokes `/handback`, directly or via the
   natural-language skill ("hand back this story," "wrap up the evidence for this
   branch").
3. **If commands were captured:** `docs/studious/handback/<branch-slug>.md` lands,
   committed, on the branch — a manifest of exactly what ran and passed/failed, plus a
   summary grounded in the actual diff and evidence. A later `/gate-audit` or
   `/gate-acceptance` run, a human reviewing the PR, or a future story picking this
   branch back up has one file to read instead of a lost transcript.
4. **If nothing was captured** (a docs-only or design-phase story, like this one — this
   design doc's own branch runs no verification commands, so its own future `/handback`
   invocation would correctly report "no log" rather than commit a hollow file): the
   worker is told exactly that, and moves on. No fabricated confidence, no clutter.
5. `gates-cite-evidence` (a sibling story, not built here) reads the *raw* evidence log
   directly for its own citations — it does not depend on `/handback` having run.
   `/handback`'s output is for human/board continuity, not a machine dependency in the
   gate path; a gate never needs to wait on a worker's separate handback action to cite
   evidence that already exists in the log.

## Out of scope

- **Winnow's Phase-3 formal capsule schema.** Issue #97 says explicitly not to wait
  for it. `docs/studious/handback/<branch-slug>.md` is a plain, clearly-provisional
  markdown doc — two prose/table sections, not a JSON object claiming conformance to a
  spec that doesn't exist yet. A future story reconciles the shape once winnow's Phase
  3 lands; this one doesn't guess at it.
- **Automatic invocation from `/work-through`'s driver.** The epic's own goal
  statement scopes this work to "gate-ledger's existing write choke points with **no
  new instrumentation**" — wiring `workflows/epic-driver.js` to call `/handback`
  automatically at the end of every build-phase dispatch is new instrumentation to the
  driver, not a write-choke-point reuse, and the acceptance criteria describes an
  invocable skill, not a mandatory step. A natural follow-up once this lands and its
  actual value is observed (the epic's parent issue #97 carries its own kill rule —
  *"after 3–4 dogfooded stories, if receipts never changed a gate verdict or a human
  decision, stop"* — which this story's opt-in shape keeps checkable rather than
  pre-committing to).
- **Wiring `reference/worker-contract.md`'s "what a worker must return" table to
  require a handback.** Same reasoning — ships as a standalone capability now; making
  it mandatory is a separate, later decision once it's proven useful.
- **A capsule when no evidence log exists.** The acceptance criteria's no-log branch is
  explicit: report, don't fabricate. No stub file, no placeholder manifest.
- **Cross-branch or epic-wide aggregation.** One branch's log in, one branch's capsule
  out — the same per-branch scope `evidence-capture-hook` already established for the
  log itself.
- **Changing `gates-cite-evidence`'s reading path.** That story reads
  `.studious/evidence/<branch-slug>.jsonl` directly, per its own criteria ("cite a
  specific evidence-log entry"); this story's manifest doc is not in its dependency
  path, and this design doesn't add one.
- **DSSE-signed envelopes, sigstore, driven-flow recordings, screenshot pairs** — the
  same winnow Phase-2 Exhibit machinery `reference/evidence-format.md` already
  excludes from the log itself; the capsule built on top of that log inherits the same
  boundary.
- **A verdict or gate vocabulary for handback.** It isn't a gate. No entry in
  `reference/gate-vocabulary.md`, no PASS/FAIL, nothing for `/work-on` to branch on.

## Alternatives considered

**Have `gates-cite-evidence` read the manifest instead of the raw `.jsonl`.** Simpler
in one sense — one canonical "formatted" evidence artifact instead of two readers of
the raw log. Rejected: it would make gate citations only as fresh as the last
`/handback` run rather than live, and it manufactures a hard sequencing dependency
(gates now need handback to have run first) the epic DAG doesn't actually impose —
both stories depend only on `evidence-capture-hook`, deliberately siblings, not a
chain. The raw log is already plain, one-object-per-line JSON, directly `jq`-able; a
gate reading it live is no harder than reading a formatted intermediate, and it stays
correct even if a worker never ran `/handback` at all.

**A JSON capsule guessing at winnow's future Phase-3 shape.** Considered, since it
would make a later migration to the real schema a smaller diff. Rejected: guessing now
is precisely the risk the epic pre-mortem's item 1 (Exhibit-format drift) names —
better to ship something honestly provisional (plain markdown, no schema claim) than a
JSON file whose field names silently imply spec conformance it doesn't have. Waiting
for a real spec before serializing anything schema-shaped is the safer failure mode.

**Auto-generate the summary from the evidence log alone (no worker narrative).** Would
remove the one step that needs judgment rather than mechanics — a template like "N
commands ran, M passed" from the log's own PASSED/FAILED counts, no prose. Rejected as
the sole content: it can't say *why* anything happened, only *that* something ran,
which is exactly what the raw log already shows without a capsule at all. Kept as a
fallback the summary section can *lean on* (record counts, pass/fail split) but not
replace the narrative with — the manifest table already covers the mechanical part;
the summary's job is the part only the worker's own context can supply.

**No commit — return the capsule content in the worker's own response text only.**
The literal minimum that could satisfy "a written summary" without ever touching git.
Rejected outright: the acceptance criteria says "committed to the branch," and an
uncommitted capsule has exactly the durability problem this story exists to fix — gone
the moment the session ends, same as the status quo it's replacing.

## Operational readiness

- **Migration.** Pure addition: one new command, one new skill, one new `gate-ledger`
  read verb (`evidence-list`), one new committed-doc convention
  (`docs/studious/handback/`). No existing store's shape changes; `evidence-append`'s
  write path and record shape are untouched.
- **Rollback.** Revert the command/skill files and the `evidence-list` verb. Any
  `docs/studious/handback/*.md` files already committed are inert plain markdown —
  nothing else reads them (see Out of scope: `gates-cite-evidence` reads the raw log,
  not this doc) — so rollback carries no data-loss risk to the evidence log or any
  other store.
- **Rollout.** Ships in the plugin's normal semantic-release cadence; every consuming
  project picks it up on next plugin update, same as `evidence-capture-hook`. Unlike
  the hook, `/handback` has no passive, always-on surface — it only acts when
  explicitly invoked, so there's no blast-radius concern equivalent to a hook firing on
  every `Bash` call project-wide. Degrade-silently on missing `git`/`jq`, mirroring
  every other `gate-ledger`-backed command: report the tool is missing rather than
  half-commit a partial file.
- **How we'll know it's working or failing.** No server, no metrics backend — the
  committed `docs/studious/handback/<branch-slug>.md` files are themselves the signal,
  directly inspectable per branch. Build-phase tests exercise both branches
  concretely: a branch with a populated evidence log produces the expected manifest
  content and commits it; a branch with no log (or an empty one) commits nothing and
  returns the no-log message. The real-world signal is issue #97's own dogfood plan
  (studyengine #210, then #209) and its kill rule — this story doesn't have to satisfy
  that rule itself, but shipping `/handback` as an explicit, opt-in action (rather than
  forced into every dispatch) is what keeps the kill rule checkable rather than having
  already pre-committed the epic to "handback always runs" before anyone has observed
  whether its output changes a single gate verdict or human decision.

## Open questions

- **Where does the summary's grounding material come from when there's no design
  doc** — e.g. a story with only a build phase run interactively, no recorded
  `designDoc` in its work file? The proposed design leans on `git log`/diff as the
  fallback grounding source; whether that's sufficient in practice, or the command
  needs an explicit pointer to the work file's recorded context, is worth watching
  during the first real dogfood run rather than resolved by assumption here.
- **Naming: `/handback` vs. a `work-`-prefixed name** (`work-handback`, matching the
  `work-on`/`work-through` family). This design picks the bare name because it's the
  exact, already-distinctive term `reference/worker-contract.md` and issue #97 both
  use verbatim, and prefixing it adds a hyphen without adding clarity within a domain
  where "handback" is already unambiguous. Flagged for `/gate-design-review` to weigh
  in on directly, since naming-convention adherence is exactly its kind of call.
- **Multiple handbacks across phases on one branch.** This design overwrites a single
  per-branch file each time `/handback` runs (git history holds prior states). Whether
  a later story wants per-phase capsules instead (one for design, one for build) isn't
  decided here — nothing in the acceptance criteria asks for it, and the log itself has
  no phase boundary markers to split on today.
