---
description: Drive a whole milestone or epic through the gate flow with dispatched agents — plan once for approval, then run everything runnable, stopping only for judgment calls
argument-hint: "[milestone, epic issue, or label] (omit to keep driving the epic in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Workflow
---

# Work through an epic

Drive a whole milestone through the same gate flow `/work-on` walks one piece at a
time. This command owns state assembly and reporting; a deterministic Workflow script
owns scheduling (which stories run, in what order, retry caps, merge order); dispatched
agents own every judgment. Code owns bookkeeping; prompts own judgment. Two modes,
resolved by state rather than flags: no epic in flight → the plan piece; an approved
epic → the driver.

**The posture — non-negotiable:**

- **Gates are unbypassable.** Gate agents run the gate commands' workflows verbatim;
  never soften, reinterpret, or skip a verdict. Tokens are canonical in
  `reference/gate-vocabulary.md`.
- **Lanes stay separate.** Gate agents never build; worker agents never gate
  (`reference/worker-contract.md`); the two never share context. A gate judges the
  diff and the doc, never a worker's transcript.
- **GitHub is read-only.** Never create or edit issues; never open PRs — after the
  finale the branch is the user's (`gh pr create`).
- **Judgment verdicts always stop the story** and wait for the user. Autonomy never
  absorbs a RETHINK, NEEDS DISCUSSION, or HOLD; unknown verdicts park too, never
  advance.
- **Nothing runs before the user approves the plan.**

Read PRODUCT.md at the project root first. If `gate-ledger` is not on `PATH`, stop —
this flow cannot run without recorded state. Say so and point at `/work-on` for the
supervised, evidence-first flow instead.

## Resolve the epic

`gate-ledger epic-list` shows epics in flight (slug, status, landed/total, branch, title).

- **`$ARGUMENTS` is empty** — if exactly one epic has status `approved`, `running`, or
  `ready`, drive it. If several, list them and ask which — don't guess. If none, invite
  `/work-through [milestone, epic issue, or label]`.
- **`$ARGUMENTS` matches an epic in flight** (slug or title) — drive that one.
- **Anything else starts a new epic.** Resolve it read-only with `gh`:
  - a milestone name or number → `gh issue list --milestone "<M>" --state open --json number,title,body,labels`
  - an issue reference → `gh issue view <N> --json number,title,body` (for an epic
    issue, follow its checklist and linked issues too)
  - a label → `gh issue list --label "<L>" --state open --json number,title,body,labels`

  Then run the plan piece.

## Plan piece — runs once, ends at approval

1. Read PRODUCT.md, DESIGN.md, and CLAUDE.md.
2. Propose a decomposition satisfying `reference/epic-plan-contract.md`: stories with
   slugs, source issues, acceptance criteria, dependency edges, a gate profile each, an
   epic goal statement, a concurrency cap, and an epic pre-mortem. Present the whole
   plan — the user can only approve what they can see.
3. Stop and iterate. The user trims, reorders, re-scopes, drops. Nothing is recorded
   and nothing runs until they explicitly approve.

4. **Settle the open forks in one interview — the epic's only scheduled human turn.**

   Every dispatched phase runs in a subagent with no human in its loop. A worker that
   meets an unanswered product fork can only guess or park, and a guess is worse. So
   the forks get answered here, once, for the whole epic.

   Collect the questions across all stories, then admit only those that are **both**:

   - **product or scope level** — which surface, which persona, what's in and out,
     which of two behaviours is correct; *not* which abstraction or library, which
     gets discovered mid-build and depends on what the earlier stories produced; and
   - **answerable now** — nothing in an unbuilt story's output changes the answer.

   **Cap the session at 10–12 questions for the entire epic**, prioritised by how much
   rework a wrong assumption causes. That is roughly two per story on a five-story
   epic — deliberately far below what a per-story interview would ask, because this
   session buys unattended execution, not exhaustive specification. Everything cut
   stays available: a worker that hits it parks, and the story surfaces in "Needs you".

   Skip the session outright when nothing qualifies; say so rather than manufacturing
   questions to fill a quota.

   If viva is installed, run it as one batch. `QAInput` is a flat question list with a
   single `context` string and no grouping field, so **the story slug goes in each
   question's `id`** (`<story-slug>-<n>`) and opens its `text` — no viva change is
   needed. Give every fork 2–3 `choices` and, where you have a defensible view, one
   `recommended_choice` (it must match a choice exactly; it renders as advice and is
   never preselected).

   ```bash
   # .viva/qa-input.json — see viva's docs/headless-contract.md §3 for the shape
   jq -n --arg ctx "Epic <slug> — settling <n> forks before the driver runs" \
     '{mode: "qa", context: $ctx, questions: $qs}' --argjson qs "$QUESTIONS" \
     > .viva/qa-input.json
   ```

   Then invoke `/viva-qa` and read `.viva/answers.json`. If viva is **not** installed,
   ask the same questions in the conversation — the point is that a human answers them
   before dispatch, not that viva mediates it.

5. On approval, record exactly what was approved. Derive `<slug>` from the epic title:

   ```bash
   gate-ledger epic-set --slug "<slug>" --title "<title>" --source "<milestone M | issue #N | label L>" \
     --goal "<goal statement>" --branch "epic/<slug>" --concurrency <cap> --status approved
   gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --title "<story title>" \
     --source "issue #N" --criteria "<criteria>" --decisions "<answered forks>" \
     --deps "<dep-a,dep-b>" --gates "<profile>"
   ```

   `--decisions` carries that story's answers as one line — `fork: answer; fork: answer`
   — distilled from `.viva/answers.json` (`choice`, plus `note` when the human added
   one). It reaches every dispatch prompt through the driver's shared context block,
   marked settled and not to be re-litigated. Omit the flag for a story with no
   answered forks; keep acceptance criteria in `--criteria`, where they belong.

   One `epic-story-set` per story, then:

   - Write the epic pre-mortem register to `docs/studious/premortems/<slug>-epic.md`
     and record it: `gate-ledger epic-set --slug "<slug>" --premortem "<path>"`.
   - Create the integration branch **from the default branch — never from whatever
     happens to be checked out** — and give it its own worktree, leaving the user's
     checkout untouched:

     ```bash
     default=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
     git branch "epic/<slug>" "${default:-main}"
     git worktree add ".studious/worktrees/<slug>/__epic" "epic/<slug>"
     ```

6. Close with the report block below. Driving starts on the next invocation — approval
   and execution never share one.

**No human approves a design doc on this path. State that plainly to the user at
approval time — don't let them discover it at the epic PR.**

The driver's default profile is `design → design-review → build → audit → acceptance`:
a dispatched worker drafts the design doc and `/gate-design-review` reviews it against
`reference/design-doc-contract.md` on every story. Two constraints force this, and
neither is a preference:

- **A subagent cannot open a browser.** viva's sign-off is a human at a keyboard, and
  there isn't one inside a dispatched phase running three-at-a-time in parallel
  worktrees.
- **The driver may not name a build skill.** `workflows/epic-driver.js` is on the gate
  surface `scripts/check_gate_independence.py` guards, so it dispatches a worker
  against `reference/worker-contract.md` rather than routing to `/design`. That rule is
  what keeps a gate from caring who built the branch; it also means the epic path can't
  inherit `/design`'s sign-off loop even if a human were available.

So the human turns at epic scale are: the story-plan approval, this interview, and the
PR. `/gate-design-review` reviews every design doc, but an agent reviewing is not a
human approving — do not describe it to the user as an equivalent substitute. What
front-loading moves is the **interview**, which has no substitute at all; the sign-off
is genuinely reduced, not relocated.

Story-scale work through `/work-on` keeps the human in every round — a design doc there
gets both a viva sign-off and the gate. The inconsistency between the two scales is
known and tracked (issue #210); it is not a licence to improvise a third behaviour here.

## Driver — every later invocation

If the epic's status is still `approved`, mark the run started:
`gate-ledger epic-set --slug "<slug>" --status running`.

### 1 · Reconcile — evidence first

Recorded state must match evidence before anything is dispatched; evidence wins, and
the files get corrected (via `gate-ledger`, never by hand) when they disagree. One
call resolves all of it:

```bash
reconcile_json=$(gate-ledger epic-reconcile --slug "<slug>")
```

`$reconcile_json`'s `.epic` field is the same epic-and-stories state a bare `epic-get`
returns. Each `.stories.<story>` entry (keyed by the bare story slug) carries that story's
work-file state (`.work` — every epic-dispatched work file is recorded under the
epic-qualified slug `<slug>--<story>`, never the bare story slug, but this payload
already keys it back to the bare slug for you; `null` if the story hasn't reached
`design` yet — see Record keeping), its gate verdicts at the story branch's HEAD
(`.gate`, `null` if no gate has ever run; a passing verdict counts only when
`.storyBranchHeadSha` matches the verdict's own recorded sha), its story-branch HEAD
sha (`.storyBranchHeadSha`, empty if the branch doesn't exist yet), whether its
recorded `designDoc` exists on disk (`.designDocExists`), and whether a story recorded
`landed` is actually merged onto the epic branch (`.landedButUnmerged`) — a `landed`
story with `landedButUnmerged: true` isn't landed; flag it and correct the recorded
status via `gate-ledger` rather than trusting it.

From the reconciled state, derive each unfinished story's **next phase** (first phase
in its gate profile whose evidence is missing) exactly as before. One special value: if
every profiled gate has already proceeded at the story branch's HEAD and only the merge
onto the epic branch is missing, the next phase is the sentinel `merge` — the script
jumps straight to landing the story instead of re-running its profile.

**Mark the run boundary, before anything dispatches.** A story's work file only exists
if some invocation already started it — this one runs Reconcile first, before any
dispatch, so "the file already exists" can only mean an *earlier* invocation created
it. For each such story (skip a brand-new story with no work file yet — its first
phase measures against the work file's own `createdAt`, unchanged), derive this
story's work-file JSON from the already-captured `$reconcile_json` — its
`.stories["<story>"].work` field is the same content a standalone `work-get` would
return, no extra `gate-ledger` call needed — and write one marker unless the last
entry is already one or the derived next phase is the `merge` sentinel (nothing ever
reads `history` again for a story that's only got its merge left):

```bash
work_get_json=$(echo "$reconcile_json" | jq -c '.stories["<story>"].work // empty')
last_step=$(echo "$work_get_json" | jq -r '.history[-1].step // ""')
if [ -n "$work_get_json" ] && [ "$last_step" != "run-boundary" ] && [ "$next_phase" != "merge" ]; then
  gate-ledger work-log --slug "<slug>--<story>" --step "run-boundary" --outcome "DISPATCHED"
fi
```

`run-boundary` is a reserved `step` name — it collides with nothing in the gate/worker
phase vocabulary (`design`, `design-review`, `build`, `audit`, `acceptance`, `merge`)
and `/work-on`'s own `history` reader filters on an exact different step name, so it
never sees or misreads this entry. This exists solely so the closing report's duration
render (below) can tell a real same-run predecessor apart from idle/inter-invocation
time — see [#142](https://github.com/jacquardlabs/studious/issues/142) for the full
rationale, including why this is a convention over the existing free-form `--step`/
`--outcome` arguments rather than a new `gate-ledger` verb or schema change.

### 2 · Run the driver script (primary mode)

The scheduler is code, not prose. Resolve the plugin root (the plugin's `bin/` is on
`PATH`, so the ledger's location reveals it):

```bash
plugin_root="$(cd "$(dirname "$(command -v gate-ledger)")/.." && pwd)"
# driver script: $plugin_root/workflows/epic-driver.js
```

Read `${plugin_root}/reference/prompt-contract.md` once (the same plugin-root
resolution the four gate commands use; if it isn't there, locate
`reference/prompt-contract.md` inside the plugin install with Glob — never guess a
path or skip this read). The script has no hands to read a file itself: hand it the
five blocks — the injection-defense preamble, the read-only/diff-scope convention, the
output-row schema, the calibrate-don't-suppress closer, and the writing-style rules —
verbatim as `args.contract`, so it can stamp them into every audit and premortem dispatch it
builds, per-story and at the finale, exactly as the four gate commands stamp them into
their own Task dispatches. This is the whole handoff — no runtime-pointer resolution
happens on this path. The script fails closed at any dispatch that needed the contract
if it arrives empty or missing, so treat a missing file here as a stop, not a skip.

Call the Workflow tool with `scriptPath` set to that file and `args`:

```json
{
  "epic": "<$reconcile_json's .epic field, verbatim — no second epic-get call>",
  "phases": { "<story>": "<next phase>" },
  "repoRoot": "<absolute path of the main working tree>",
  "defaultBranch": "<resolved default branch>",
  "contract": "<reference/prompt-contract.md's five blocks, verbatim>",
  "timestamp": "<current ISO time>"
}
```

The script schedules the DAG under the concurrency cap, dispatches workers
(`reference/worker-contract.md`) and gates, applies the verdict rules mechanically
(fix-and-retry verdicts: fixer + fresh-eyes gate re-run, capped; judgment verdicts:
park immediately), merges each story when its **final profiled gate** returns its
proceed token, and runs the epic finale when everything has landed or been dropped.
Every state mutation is written by the agent that caused it, via `gate-ledger` — the
script's memory is a working copy, so a killed run resumes by re-running this command:
reconcile, re-invoke, nothing duplicated or lost.

Render the script's return value in the fixed report shape below. Do not re-derive or
second-guess its scheduling; anything it parked is the user's, not yours to retry.

### Fallback driver — use only when the Workflow tool is unavailable

Semantics are identical to the script's (defined once in the design doc) for
everything except scope-delta measurement (#244): walk each runnable story's next
phase with dispatched agents — runnable = every dependency `landed` ∧ not
`parked`/`dropped` ∧ under the epic's cap — dispatching independent stories in
parallel (one message, multiple Task calls). Workers follow
`reference/worker-contract.md`; gate agents run the gate command workflows and
record their own verdicts from inside the story worktree. Design-review and
acceptance need no extra step — the single dispatched agent reads its gate command
and self-injects exactly as it would from the script path. Audit is different here
too: read `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` yourself (same
anchored resolution, Glob fallback if it doesn't substitute) and stamp its five
blocks into every audit and premortem Task prompt you dispatch in this mode — you
are the assembly point on this path exactly as your own read is on the script path.
Log every step with
`gate-ledger work-log --slug "<slug>--<story>" --step <phase> --outcome "<token>" --phase "<next phase>"`
(the same epic-qualified slug as script mode — see Record keeping). When `<phase>`
is exactly `audit` or `acceptance` — the only two steps the script itself ever
measures a scope-delta moment at — append `--scope-delta-phase "<phase>" --scope-delta-unmeasured`
to that same call, zero new dispatch. Never append it for any other step (`design`,
`design-review`, `merge`, `run-boundary`): the script never measures those either,
so marking them unmeasured would manufacture moments the closing report has no
business counting.

**Scope-delta measurement does not run on this path in round one** — no equivalent
of the script's own per-moment naming (`workflows/epic-driver.js`'s `scopeDeltaPhase`:
`build` for audit's first round, `<gate>-fix-<N>` for each retry). That logic lives
only there; this fallback prose does not reimplement it, and no `--declared-files`
flag is ever part of any call on this path (declaring files stays a `/design`-time,
script-and-fallback-shared step at `work-set`, untouched by this section). What the
`--scope-delta-phase`/`--scope-delta-unmeasured` pair above adds instead is
deliberately partial: it marks the step itself (`<phase>`, literally `audit` or
`acceptance` — never the script's own `build`/`<gate>-fix-<N>` moment name) as an
unmeasured entry, so the closing report's `scope:` line renders a real
`moment(s) unmeasured` count for it instead of silently reflecting nothing.
`computeScopeDelta`'s own `files`/`declaredFiles` comparison and its `outsideFiles`
count never run here — this is a marker that a moment went unmeasured, not a
measurement. A story driven entirely by the script mode keeps accumulating real
`scopeDelta` entries as usual; a story that switches to this fallback mode
mid-epic starts recording unmeasured markers at its audit/acceptance steps from
the switch onward instead — visible in the same summary, never a silent gap. This
is a stated round-one limitation of the driver-only design, not a claim that the
two modes fully agree on everything they do.

Apply verdicts exactly as the script does:

- **Proceed** → the story's next profiled phase; when the **final profiled gate**
  proceeds at story HEAD (SHIP for a full profile; whatever its last gate's proceed
  token is for a trimmed one), merge in the `__epic` worktree (`git merge --no-ff`,
  one merge-fix attempt, abort → park), then
  `epic-story-set --epic "<slug>" --slug "<story>" --status landed`,
  `work-log --slug "<slug>--<story>" --step merge --outcome LANDED --phase done`, and
  `git worktree remove ".studious/worktrees/<slug>/<story>"` (keep the branch). The
  work-log write is not optional bookkeeping: this step deliberately keeps the branch,
  so a terminal phase is the only thing that ever closes the work file out and lets
  `gate-ledger gc` collect it. Without it the story stays an "active feature" in
  `/work-on` forever (#237).
- **Fix and retry** → `epic-story-set --epic "<slug>" --slug "<story>" --bump-retry
  <gate>`; park once the recorded counter exceeds 2; otherwise a fixer agent (never
  re-runs the gate), then a fresh gate agent.
- **Judgment or unknown** → park immediately:
  `epic-story-set --status parked --reason "<gate>: <verdict> — <one clause>"`.

## Epic finale

When every story is `landed` or `dropped` (the script runs this itself; in fallback
mode, run it in the `__epic` worktree):

1. The audit fan-out across the full epic diff (against the merge-base with the
   default branch) — the cross-story integration pass no per-story audit saw.
2. `/gate-acceptance` against the epic goal statement, not any single story.
3. `@agent-premortem-auditor` over the epic pre-mortem register.

Verdicts record to the epic branch's ledger — the PR-time hook reads the same file.
All pass → `gate-ledger epic-set --slug "<slug>" --status ready`, then release the
integration checkout so the branch is checkoutable from the user's clone:
`git worktree remove ".studious/worktrees/<slug>/__epic"`. Recap every story's verdict
trail and remind the user the PR is theirs (`gh pr create` from the epic branch).

A finale gate (audit or acceptance) whose fix cycles run out while it still holds its
own retry token (`FIX AND RE-AUDIT` / `FIX AND RE-CHECK`) does not end the run reading
as an unexplained "not ready": it adds one entry to the "Needs you" queue below naming
the epic, not a story — `<epic-slug>--finale: <gate> returned <verdict> — stalled past
2 fix cycles`. It is not a `/work-on`-resolvable story like the other entries in that
queue; investigate the epic worktree directly, or amend and re-run `/work-through`.

## Skips, amendments, and un-parking

Gate profiles fixed at plan time are the only built-in skip mechanism. Mid-flight,
skip a gate only on the user's explicit say-so — log it
(`work-log --slug "<slug>--<story>" --step <gate> --outcome SKIPPED`) and never on
your own initiative.

Amendments go through this command, never hand-edited state:

- **Un-park** — the driver never un-parks on its own. When the user resolves a parked
  story (answers the question, revises the design, accepts a risk), record it so the
  next run schedules the story with fresh fix cycles:

  ```bash
  gate-ledger epic-story-set --epic "<slug>" --slug "<story>" \
    --status pending --reason "resolved: <one clause>" --reset-retry <gate>
  ```

- **Drop** — `epic-story-set --status dropped`, remove the story's worktree if one
  exists, then re-evaluate dependents: a dependent of a dropped story needs the user
  to confirm it still makes sense.
- **Add** — a scoped plan piece for just that story (a `/gate-should-we-build` pass
  plus explicit approval of its DAG placement) before it joins the schedule.

## Close every invocation the same way

Before rendering, reconstruct each reported story's phase-duration chain from its own
recorded history — the same by-hand comparison issue #142's reporter did, made
mechanical. For every `landedThisRun` entry and every `needsYou` entry that names an
actual story (i.e. has a `<slug>--<story>` work file — the epic finale's own stalled-gate
pseudo-entry below does not and falls through the degrade rule at the end of this
section unchanged), read `gate-ledger work-get --slug "<slug>--<story>"` — one more read
of the same kind Reconcile already made per story, scoped only to the stories this
report is about to print — and, for each real phase entry in its `history` array,
compute elapsed time as that entry's `at` minus the previous entry's `at` (or the work
file's own `createdAt` for the first entry, which has no predecessor) — **except** a
phase whose immediate predecessor is a `run-boundary` marker (written by Reconcile
above): its true predecessor is idle/inter-invocation time, not work, so it renders an
explicit `(resumed)` tag instead of a computed number — one that states plainly, in its
own literal text, that no same-run duration was measured and that a manual
`gate-ledger work-get` check may be worth taking, never a bare render, never a bare
`(resumed)` label standing alone, and never a misleading number:

```bash
gate-ledger work-get --slug "<slug>--<story>" | jq -r '
  .createdAt as $created |
  [(.history // [])[]] as $h |
  [range(0; ($h | length))] | map(
    ($h[.]) as $entry |
    if $entry.step == "run-boundary" then empty
    else
      (. > 0 and $h[. - 1].step == "run-boundary") as $resumed |
      if $resumed then "\($entry.step): \($entry.outcome) (resumed — no same-run duration; worth a gate-ledger work-get check)"
      else
        (if . == 0 then $created else $h[. - 1].at end) as $prev |
        (try (($entry.at | fromdateiso8601) - ($prev | fromdateiso8601)) catch null) as $secs |
        if $secs == null or $secs < 0 then "\($entry.step): \($entry.outcome)"
        else "\($entry.step): \($entry.outcome) (\(($secs / 60) | round)m)"
        end
      end
    end
  ) | join(" → ")
'
```

Render the joined chain in place of (not appended to) the driver's collapsed
`trail`/one-clause verdict text — the whole trail for a `landedThisRun` story; a
parenthetical under the existing headline line for a `needsYou` entry. This surfaces
every recorded round, including a fix-cycle round the driver's own in-memory `trail`
collapses to its terminal verdict — issue #142's own 117-minute round renders right
next to the `SHIP` that eventually followed it, not lost to it.

Three things this deliberately does, per
[#142](https://github.com/jacquardlabs/studious/issues/142):

- **Never asserts health.** Every phase gets a number or the `(resumed)` tag, always —
  nothing here decides or says "slow," "stalled," or "retried." A human reads the
  numbers (and the tag, when present) and decides whether one is worth investigating,
  same as the issue #142 reporter did by hand.
- **A resumed phase is always flagged, never silently bare, and the flag says why.**
  A phase immediately following a `run-boundary` marker gets the
  `(resumed — no same-run duration; worth a gate-ledger work-get check)` tag whether
  the actual dispatch behind it took 5 minutes or 117 — the tag can't and doesn't claim
  to tell those apart (doing so would need the marker's own timestamp, rejected in the
  design doc on queueing-delay grounds), but its own literal words state plainly that no
  same-run duration was measured and invite the same manual check the issue #142
  reporter took by hand, rather than reading as a benign lifecycle fact a scanning
  maintainer could pass over. A fully bare render — or a bare `(resumed)` label that
  names the lifecycle event without saying to do anything about it — hides a genuinely
  slow resumed gate as easily as it hides a healthy one; the explicit wording exists
  precisely so that never happens silently.
- **Renders full history, not just this run's phases.** A resumed story's `history`
  carries every prior run's phases too; that's intentional, not a bug to fix — the
  chain is the story's complete gate-flow record to date, not a diff against the last
  invocation.

Degrade per-story, never abort the whole report: if a story's `work-get` read fails,
its `history` is empty, or the computation above errors (a missing `createdAt`, a
malformed `at`) for one entry or the whole story, render that one story's line with
the driver's own trail/reason text exactly as it would render without this step —
never a raw jq error, never "NaN," never a negative number, and never at the cost of
any other story's line in the same report.

### Scope-delta line (#244)

A second, independent read of the same per-story work file — never entangled with the
duration-chain computation above, which has its own degrade rule and its own tests.
For every `landedThisRun` entry and every `needsYou` entry that names an actual story
(same scoping as the duration chain above), compute:

```bash
gate-ledger work-get --slug "<slug>--<story>" | jq -r '
  def plural(n; noun): "\(n) " + noun + (if n == 1 then "" else "s" end);
  (.declaredFiles // null) as $declared |
  (.scopeDelta // []) as $sd |
  (.amendments // []) as $am |
  if $declared == null then "scope: unmeasured (no declaration recorded)"
  elif ($sd | length) == 0 then "scope: declared \($declared | length), not yet measured (no moment recorded)"
  else
    ([$sd[] | select(.unmeasured != true)] ) as $measured |
    ($measured | length) as $measuredCount |
    ([$sd[] | select(.unmeasured == true) | .phase]) as $unmeasuredPhases |
    # "One file counts once" is enforced authoritatively by
    # workflows/epic-driver.js's computeScopeDelta, against every prior
    # moment's own already-written history — `| unique` here is a display-side
    # idempotency guard over data that function already made disjoint, not a
    # second place this rule is decided. If this total and the driver's own
    # per-moment writes ever disagree, trust the driver.
    ([$measured[] | .outsideFiles[]?] | unique) as $outside |
    ([$measured[] | {phase: .phase, n: (.outsideFiles | length)} | select(.n > 0)]
      | map("\(.n) at \(.phase)") | join(", ")) as $byMoment |
    ([$am[] | .file] | unique) as $amendedFiles |
    ([$amendedFiles[] | select(. as $f | $outside | index($f) != null)] | length) as $amendedCount |
    (($amendedFiles | length) - $amendedCount) as $orphanedAmendments |
    ("scope: declared \($declared | length), outside \($outside | length)"
      + (if ($byMoment | length) > 0 then " (\($byMoment))" else "" end)
      + (if $amendedCount > 0 then ", \($amendedCount) amended" else "" end)
      + (if $orphanedAmendments > 0 then
          ", " + plural($orphanedAmendments; "amendment")
          + (if $orphanedAmendments == 1 then " references " else " reference " end)
          + "no counted file"
        else "" end)
      # Not bracketed, never omitted here: every moment recorded is either
      # measured or unmeasured, so this clause always has at least one to
      # report on — a moment that never got recorded at all is a different,
      # already-distinct failure the two branches above this one render
      # (unmeasured/not-yet-measured), never this one reading as a false
      # all-clean "outside 0".
      + ("; " + plural($measuredCount; "moment") + " measured"
          + (if ($unmeasuredPhases | length) > 0 then ", \($unmeasuredPhases | length) unmeasured" else "" end))
      + (if ($outside | length) > 0 then ": " + (($outside[0:5]) | join(", "))
          + (if ($outside | length) > 5 then " +\(($outside | length) - 5) more" else "" end)
        else "" end))
  end
'
```

Render the result as one line under the story's headline (below the duration-chain
parenthetical for a `needsYou` entry; below the trail for a `landedThisRun` entry),
followed by the retrieval verb itself so the reader can pull the full declaration and
any amendment reasons (neither is printed inline — the reason is a work-file-only
detail, same as the declared set): `gate-ledger work-get --slug "<slug>--<story>"`.
A story with no declaration renders `unmeasured`, never a bare omission and never a
manufactured zero — the same failure-path rule the design doc states for a failed
diff resolution. Degrade the same way the duration chain does: a failed read or a
jq error renders nothing for this line rather than aborting the story's own report
entry, and never affects any other story's line.

This line carries no verdict effect — round one measures only (no park, no retry
refusal, no threshold); it exists so the two motivating failure modes (a story that
grew unnoticed, a story that stayed near its declaration) are visible in the same
summary the human already reads, for both a parked story and a landed one.

`amended` only ever counts an amendment whose `.file` matches some moment's own
`outsideFiles` entry — an amendment can never subtract from `outside`, by
construction (the two counts are computed from disjoint fields; the amendment
never touches `scopeDelta`). An amendment naming a file that never appears in any
moment's `outsideFiles` — declared already, or a path that doesn't match what git
actually reported — drops silently out of that count with nothing to say so unless
this line names it: the trailing `amendment(s) reference no counted file` clause is
that signal, so a wrong or stale amendment reads as a visible discrepancy rather
than a quietly lower `amended` number.

The `; <N> moment(s) measured[, <M> unmeasured]` clause is the denominator: without
it, a moment that was never recorded at all (a dropped or mistyped work-log flag,
or the fallback driver's own documented gap above) renders identically to a moment
that measured clean, both reading as the same `outside <N>` number with nothing to
tell them apart — exactly the false-clean reading the AC's "never summed as zero"
rule exists to prevent. It fires whenever the `else` branch above does (at least one
`scopeDelta` entry recorded, measured or not) and is never itself bracketed or
omitted; only its own trailing `, <M> unmeasured` addendum drops when every recorded
moment was measured.

End with exactly this shape and nothing after it:

```text
Epic: <slug> — <landed>/<total> landed, <parked> parked, <blocked> blocked on them.
Needs you:
  - <story>: <gate> returned <verdict> — <one clause: what's needed>
    (<phase>: <outcome> (<Nm>) → <phase>: <outcome> (<Nm>) → ...)
    <scope line>
    gate-ledger work-get --slug "<slug>--<story>"
Landed this run: <story> — <phase>: <outcome> (<Nm>) → <phase>: <outcome> (<Nm>) → ...
  <scope line>
  gate-ledger work-get --slug "<slug>--<story>"
Run /work-through when you're ready, or resolve the queue first.
```

`<scope line>` is never omitted and is always exactly one of the three renderings the
jq above produces — identical composition for a `Needs you` entry and a `Landed this
run` entry, never a shortened form for one and the full one for the other:

- `scope: unmeasured (no declaration recorded)`
- `scope: declared <N>, not yet measured (no moment recorded)`
- `scope: declared <N>, outside <N> (<breakdown by moment>)[, <N> amended][, <N> amendment(s) reference/references no counted file]; <N> moment(s) measured[, <N> unmeasured][: <file, file, ..., +N more>]`

`(<Nm>)` is a computed duration for a phase whose predecessor was real same-run work;
a phase resumed across a run boundary (above) renders the
`(resumed — no same-run duration; worth a gate-ledger work-get check)` tag in that same
position instead, never omitted, never a bare `(resumed)` alone, and never a
manufactured number. Omit `Needs you:`
when nothing is parked. When the epic reaches `ready`, the last line becomes the
`gh pr create` handoff; `stopped` states what ended it. A parked story is always also
a valid `/work-on` feature — say so when the queue is non-empty; taking a story over
by hand happens inside its worktree (the story branch is checked out there), or after
`git worktree remove` on it. In the third rendering's bracketed `scope:` clauses,
`amended`, the amendment-orphan clause, and the trailing outside-file list are each
omitted individually when empty (no amendments, no orphaned amendments, zero outside
files) — never a literal `[, 0 amended]` or empty bracket rendered to the user; the
leading `; <N> moment(s) measured` clause is not bracketed and is never itself
omitted in that rendering, per its own paragraph above.

## Record keeping

All state goes through `gate-ledger` — `epic-set`, `epic-get`, `epic-list`,
`epic-story-set` for the epic; `work-set`, `work-log`, `work-get` for stories;
`gate-get` for verdicts; `epic-reconcile` composites all three read verbs plus the
design-doc-existence and landed/merged checks into the one call the Reconcile step
above makes — it never mutates, so every write above still goes through the same
verbs it always did. `work-set`/`work-log`/`work-get` key every epic-dispatched
story's work file to the epic-qualified slug `<slug>--<story>` — mirroring the
separator `epic/<slug>--<story>` already uses for branch names — never the bare story
slug alone, so a work file can never collide with an identically-named story in a
different epic or with a standalone `/work-on` feature sharing the same name.
`epic-story-set` needs no such qualifying: its own `--epic` argument already scopes it.
Use this same qualified string everywhere a story is named back to the user — the
"Needs you" queue prints it exactly as recorded, so `/work-on "<the printed slug>"`
resolves the right work file directly. State lives in the MAIN working tree's
`.studious/` no matter which worktree an agent writes from — the ledger anchors there
itself. Never hand-edit or directly read the JSON files. Worktrees live under
`.studious/worktrees/<slug>/` — gitignored, one per running story plus `__epic`,
removed as stories land and at `ready`; `git worktree list` is the recovery tool when
state and disk disagree.
