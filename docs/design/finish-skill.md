# Design: `/finish` (PR evidence table, cctx footer, follow-ups, decision patches, report)

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: `/build` now produces a real `BUILT` branch
(M4 shipped — `skills/build/SKILL.md`, `scripts/{worktree-setup,verify,
evidence-capture,status-flip}`), and studious's gates can judge it — but
nothing closes it out. `skills/finish/SKILL.md` is still the M1 stub ("Do
not invoke for actual finish work yet"). The persona is left doing, by
hand, exactly what `PRODUCT.md`'s critical user journey 1 (Full cycle)
commits to automating: reading every task's `Done means` back out of
`PLAN.md`, hunting down each item's evidence, writing a PR body, deciding
by memory which `Not-here` follow-ups are worth filing, and remembering to
delete the scaffolding before merge. This isn't hypothetical — it already
happened for real on this very project. `epic/m4-build-core`'s own closing
commit (`e6fd44e`, "Enforce principle 7: design docs and demonstrations die
at merge") is a human manually doing `/finish` step 6's cleanup clause by
hand, and that same PR's body (`#53`) is a human manually assembling the
evidence table `/finish` step 1 should have produced. Every subsequent
epic pays that same manual tax until this skill exists.

This is also the concrete unlock for the epic goal: "so a BUILT branch
(real now that M4 shipped) can be closed out end-to-end." Without this
story, `/build`'s own shipped verdict table dead-ends at `BUILT` with
nothing to invoke next — the persona's only "repeatable, verifiable
workflow" alternative is back to ad hoc PR-writing, exactly the thing
`PRODUCT.md` says jig exists to replace.

## Proposed design

One file changes behavior: `skills/finish/SKILL.md` replaces its M1 stub
with the real six-step procedure below, per the ratified handoff (§5.4).
Two small new scripts are added under `scripts/` (an evidence-freshness
re-validator and a report writer — behavior specified below, exact
CLI shapes left to the build phase per this contract's non-requirements).
No other script changes: `worktree-setup`, `verify`, `status-flip` are
unchanged, and `evidence-capture` is *reused*, not modified — it already
implements exactly the freshness rule this story's acceptance criteria
names ("timestamp ≥ last code commit"), because `/build` already calls it
once per `PASS`ed task. `/finish`'s job over that existing evidence is
promotion and re-validation, not re-capture.

Precondition, matching principle 10 (Standalone-capable) and the M0/M4
precedent that studious is a sibling, not a dependency: `/finish` runs
after a `/build` session reports `BUILT` — and, if studious is installed,
after `/gate-audit`/`/gate-acceptance` have already passed on that branch
(the pipeline in `PRODUCT.md`'s critical user journey 1). `/finish` itself
never checks for a recorded gate verdict — that would require reading
studious's own gate-ledger state, a sibling-plugin coupling `PRODUCT.md`'s
composition-via-small-contracts stance doesn't ask for. It simply assumes
the human invoked it because the branch is ready, the same trust boundary
`/build`'s own `BUILT`→"run `/gate-audit` next" hand-off already relies on.

### Step 1 — PR evidence table

For each task in the (now fully status-flipped) `PLAN.md`, `/finish` reads
its `Done means` items and their already-captured evidence — the dated
`docs/jig/evidence/<date>-<task>/` folders `/build`'s own `evidence-capture`
call wrote during Step 2.7 of its shipped workflow, each carrying a
`manifest.json` with `commit_sha`, `commit_timestamp`, and one entry per
captured artifact. `/finish` promotes this into the PR body as one row per
item: item → verification method (the item's own tier — `script` /
`test-backed` / `probe`) → evidence link → pass.

Two evidence shapes, two treatments — this is a ratified decision (handoff
§5.4 step 1; decision 7), not new judgment:

- **Text evidence** (a `script`/`test-backed` item's `verify` output —
  command, exit code, stdout/stderr, already sitting in that task's
  `results.json` artifact as the item's own `detail` field) is quoted
  **inline**, in a collapsible `<details>` block per item, directly in the
  PR body. It is never written to a new repository file — the M4 epic's
  own closing commit already established this exact pattern by hand
  (moving `docs/jig/demonstrations/`'s narrative text evidence into PR
  `#53`'s body instead of leaving it as a committed file), and `/finish`
  makes it mechanical instead of a thing a human remembers to do.
- **Image evidence** (a `probe` item whose artifact is a screenshot or
  other binary) stays exactly where `evidence-capture` already put it —
  `docs/jig/evidence/<date>-<task>/<label>.<ext>` — and is referenced by
  its raw URL (`https://raw.githubusercontent.com/<owner>/<repo>/<commit-
  sha>/<path>`), because, per the handoff's own stated reason, `gh` cannot
  upload an image into a PR body. The URL pins to the artifact's own commit
  SHA, not the branch name — see Operational readiness for why that
  distinction matters once the branch itself is deleted.

**Freshness hold (this story's own acceptance criteria, and epic
pre-mortem risk #1 by name).** Before promoting any evidence folder,
`/finish` re-validates it against the branch's own commit history — this
is a distinct check from the one `evidence-capture` already performed at
capture time, and getting the *floor* right is exactly what the
pre-mortem's risk #1 asks this doc to make explicit rather than assume:

> `/finish`'s freshness hold... is the same ordering-assumption class of
> bug #44 just found in `verify` — a producing step that commits *after*
> writing the artifact it's timestamping against makes the check
> structurally unpassable.

Issue #44's actual bug: `verify`'s probe check compares an artifact's mtime
against `--since <the executor's own commit SHA>` — but the artifact is
necessarily written *before* that commit (the executor commits as its last
act), so the check is structurally unpassable. The naive analogue here
would be: check every evidence folder's artifact mtimes against the
branch's *current* `HEAD` at `/finish`-invocation time. That reproduces the
identical shape — task 1's evidence was captured when `HEAD` was task 1's
own commit; by the time `/finish` runs, `HEAD` has advanced through every
later task's implementation commit, evidence commit, and status-flip
commit. A "must be ≥ current `HEAD`" check would fail for every task
except the very last one.

The design decision this doc makes, to avoid that: **the freshness floor
for each evidence folder is that folder's own `manifest.json` — not the
branch's current `HEAD`.** `evidence-capture` already stamped
`commit_sha`/`commit_timestamp` into the manifest at the moment it verified
freshness against the code that existed *then*; `/finish`'s hold
re-confirms two narrower, still purely mechanical things instead of
re-deriving that judgment against a moving target:

1. The manifest's `commit_sha` is still an ancestor of the branch's current
   `HEAD` (i.e., it wasn't produced on a since-rewritten or orphaned
   commit — a real risk after a REPLAN's hand-revision and rebuild).
2. Every artifact file's own mtime is still ≥ that *same* recorded
   `commit_timestamp` (catches an artifact silently touched or replaced
   after capture — a stale copy-forward from a later, unrelated attempt).

A folder that fails either check is not promoted silently — `/finish`
reports it by name and stops before assembling the PR body, naming the
specific task and reason (stale/orphaned), rather than publishing a PR
whose evidence table is quietly wrong. The human's resume action is
re-running the task's evidence capture (via `/build` or by hand) and
re-invoking `/finish`.

Any `Done means` item with **no** corresponding evidence folder at all
(possible if a task reached `PASS` by a path other than `/build`'s own
loop, e.g. a hand-verified fix) is named explicitly in the PR body as
"evidence not found for item N" rather than silently omitted or
fabricated — `/finish` does not invent evidence, and does not call
`evidence-capture` itself to backfill it (see Out of scope).

### Step 2 — cctx footer

`command -v cctx` (or the equivalent existence check) gates everything in
this step. **Not installed:** `/finish` states so explicitly in its own
output — "cctx not installed; skipping the session-cost footer and harvest
offer" plus the one-line install pointer (`pipx install cctx-cli`) — and
moves directly to Step 3. No error, no stack trace, no silent gap in the PR
body where the footer would have been: principle 10's "every degradation
graceful, none silent" applies word-for-word to this step, and this
project's own current environment (cctx is not installed here) makes this
the exact path any real demonstration of this story exercises first.

**Installed:** `/finish` runs `cctx autopsy --latest` (unmodified — cctx's
own documented contract, no jig-specific flags invented) and appends its
findings summary (verdict, findings, session cost) to the PR body as a
distinct footer section, separate from the evidence table. It then offers
`cctx harvest` interactively: runs it in **preview mode only** (no
`--apply`), shows the proposed `CLAUDE.md` diff, and stops. `--apply` is
only ever passed after the human's own explicit confirmation in that same
turn — `/finish` never invokes harvest with `--apply` as part of its own
default flow. This matches cctx's own CLI contract exactly (`cctx harvest`
previews and confirms by default; `--apply` is the caller's opt-in to skip
that prompt) and the acceptance criteria's own wording: "always
preview-confirms, never auto-applies."

### Step 3 — File survivors

Two follow-up sources, both drafted earlier in the pipeline, neither filed
until now:

- **Not-here follow-ups** — `PLAN.md`'s own `## Not-here follow-ups`
  section (bulleted, one line each), the format the M0 dogfood already
  validated (`docs/jig/dogfood/PLAN-viva-unified-session.md`) and that
  `/build`'s own task-splitting logic already treats as a coarser heading
  to exclude from any task's dispatch (`skills/build/SKILL.md` Step 1.4).
  This exists today and `/finish` reads it directly.
- **NOTES stubs** — per the handoff (§5.3), an executor's stray discoveries
  during a task ("outside Done-means... never into the diff") are meant to
  land in a NOTES stub rather than the diff. **`/build`'s M4 implementation
  does not yet write these** — `skills/build/SKILL.md` has no NOTES-stub
  step. This doc defines `/finish`'s *consumption* contract for a NOTES
  stub the same way build-skill's design doc named the rough-in inspector
  as an explicit no-op stub (issue #15): `/finish` looks for one and
  reports "0 NOTES stubs found" rather than treating their absence as an
  error, so today's real branches file real Not-here follow-ups and zero
  NOTES-derived issues — an honest, not a broken, result. See Out of scope.

For each survivor, `/finish` drafts a GitHub issue (title + body, citing
the task and `PLAN.md` line it came from) and presents the **full batch**
of drafts to the human before filing anything. Confirmation is **per-item**,
not all-or-nothing: the human accepts, edits, or skips each draft
individually. (All-or-nothing would either force-file a mediocre follow-up
to get a good one filed, or block a good one on a bad one — see
Alternatives considered.) Only `gh issue create` calls for accepted drafts
run; skipped drafts are dropped, not saved for a later run.

This is epic pre-mortem risk #3's central concern, addressed directly: no
code path calls `gh issue create` without this per-item confirmation
having already happened in the same turn.

### Step 4 — Propose decision patches

Design decisions that outlive the feature — a granted pattern exception, a
new contract convention, a ruled fork with lasting consequences — become
proposed diffs against `PRODUCT.md` / `DESIGN.md` / `CLAUDE.md`. This step
is asymmetric with Steps 2 and 3, deliberately: cctx harvest and
issue-filing both *do* write something, once the human confirms in-flow.
Decision patches **never do**, confirmed or not — `/finish` always ends
this step by printing the proposed diff blocks; it never calls a write
itself, even after an explicit "yes." "Propose; never apply" is stated
twice for this specific step (`PRODUCT.md`'s own principle list, and the
handoff §5.4 step 4 verbatim) — for cctx harvest and issue-filing,
"confirm" is the gate before an action `/finish` performs; for decision
patches, there is no such action to gate. The human copies the diff in by
hand, or runs it through their own separate process. This is the same
propose-only posture studious's own `/deep-review` reviewers already take
toward the three context docs (this project's own `CLAUDE.md`: "review
commands... propose[s]" context-doc updates, never auto-apply) — `/finish`
matches that existing convention rather than inventing a different rule
for jig's own context docs.

### Step 5 — Dated build report

`/finish` writes `docs/jig/reports/YYYY-MM-DD-<story-slug>-build-report.md`
— same class and naming shape as studious's own dated review reports
(`docs/studious/<kind>-reviews/YYYY-MM-DD-<kind>-review.md`), reusing an
established convention rather than inventing a new report shape. Contents:
a durable copy of what Steps 1–4 produced — the evidence table, the cctx
footer (or its "not installed" note), which follow-ups were filed (with
their new issue numbers) and which were skipped, and the proposed decision
patches verbatim. This is not a new document *class* under decision 12's
"no fourth document class" rule — it's explicitly named in the handoff as
"same class as studious review reports," and its home (`docs/jig/reports/`)
is not one of the paths `.gitignore` retires (`docs/design/`, `/PLAN.md`,
`docs/jig/demonstrations/`); this report is meant to survive the merge and
feed cross-cycle trend comparison, the same reason studious's own review
reports are committed rather than ephemeral.

### Step 6 — Verdict + cleanup

`/finish` reports one of four tokens and performs the matching cleanup —
this table is the direct answer to epic pre-mortem risk #4 ("a build/demo
that only exercises one verdict path... risks leaving the other three
under-specified"):

| Verdict | Meaning | Worktree | Branch | PR |
|---|---|---|---|---|
| `MERGE` | Merge straight into the target branch (no PR) — e.g. a story branch merging into its parent epic branch under studious's own orchestration, or a solo developer merging directly to `main`. | Removed | Deleted after a successful merge | None opened |
| `PR` | Open a GitHub PR carrying the assembled body (evidence table + cctx footer + filed-issue links + report link) as its description. | **Kept** — follow-up commits addressing review feedback still need it | **Kept**, un-merged, tracked by the open PR | `gh pr create` |
| `KEEP` | Preserve the branch and its work without merging or opening a PR — e.g. paused work, or a spike worth keeping for reference. | Kept | Kept | None opened |
| `DISCARD` | Abandon the work outright — e.g. an ESCALATE finding proved the direction wrong, or the branch is superseded. | Removed | Deleted | None opened |

Every verdict shares the same "design docs and `PLAN.md` die with the
branch" step (decision 12; principle 7) *before* whichever git action
happens — the cleanup commit `e6fd44e` made by hand for `epic/m4-build-core`
is the literal precedent: remove `docs/design/<slug>.md` and `PLAN.md`
(and any scratch `docs/jig/demonstrations/` narrative, if used), in a
commit whose message notes the promoted-elsewhere destination (the PR
body, for `PR`; nowhere, for a direct `MERGE`/`KEEP`/`DISCARD` with no
PR — see Open questions on what "promoted" means without a PR to promote
into). `docs/jig/evidence/` and `docs/jig/reports/` are **not** touched by
this step — decision 7's retention call ("keep post-merge... files are
small") applies to both, unchanged from what `/build` and Step 5 already
wrote.

`MERGE` and `PR` both require resolving a target/base branch. `/finish`
does not invent new plumbing for this: it uses the same base
`worktree-setup` was given when this branch was created (`--base`,
per `skills/build/SKILL.md`'s own setup step) if that's resolvable from the
worktree's git state; if it isn't confidently resolvable, `/finish` asks
the human once, by name, before acting — never guesses silently toward
`main`. See Open questions.

### Principle alignment

"Recommend one action; the human decides. Propose; never apply" is this
story's whole shape end to end: Step 3 confirms per-item before any
`gh issue create`; Step 4 never applies regardless of confirmation; Step 6
reports one verdict and waits, it does not pick one. "Nothing signs off on
itself" is why Step 1 re-validates evidence against its own recorded
commit rather than trusting `evidence-capture`'s past word forever, and why
a missing evidence folder is reported, never fabricated. "Standalone-
capable" is Step 2's explicit, named cctx-absent path. "Disposable
scaffolding, durable decisions" is Step 6's cleanup contrasted with Step 5's
report and Step 1's evidence retention. "Judgment in the model, mechanics
in scripts" is the freshness hold and the report write being scripts;
the human's per-item accept/skip and the MERGE/PR/KEEP/DISCARD choice are
the judgment calls no script makes.

## User journey

Walks `PRODUCT.md` critical user journey 1 (Full cycle), the step this
story adds:

1. The developer's branch reaches `BUILT` (`/build`), then passes
   `/gate-audit`/`/gate-acceptance` (if studious is installed) or is
   otherwise deemed ready. They invoke `/finish`.
2. `/finish` reads `PLAN.md`'s status-flipped tasks and each task's
   `docs/jig/evidence/<date>-<task>/` folder, re-validates every folder's
   freshness against its own recorded commit (not the branch's current
   tip), and assembles the PR evidence table — text inline, images by raw
   URL. Any folder that fails the freshness hold stops the run here, named
   explicitly, before a PR body is ever assembled.
3. `/finish` checks for cctx. In this project's own current environment,
   cctx is not installed: it reports that plainly and moves on — the
   developer sees no gap, no error, no silently-missing footer section. On
   a machine with cctx installed, the developer instead sees the autopsy
   footer appended, and is offered a harvest preview they can accept,
   edit, or decline.
4. `/finish` presents every Not-here follow-up (and any NOTES stubs, today
   always zero) as a drafted GitHub issue. The developer accepts three,
   edits one's title, and skips one they've decided isn't worth tracking.
   Only the four accepted/edited drafts become real issues.
5. `/finish` prints two proposed `PRODUCT.md`/`CLAUDE.md` patches from
   decisions made mid-build. The developer reads them, copies one into
   `CLAUDE.md` by hand, and decides the other isn't worth keeping — either
   way, `/finish` never wrote to those files itself.
6. `/finish` writes the dated build report to `docs/jig/reports/`,
   removes `docs/design/finish-skill.md` and `PLAN.md` from the branch (a
   distinct commit, evidence already promoted into the not-yet-opened PR
   body), and asks which of `MERGE`/`PR`/`KEEP`/`DISCARD` applies. The
   developer says `PR`; `/finish` opens it against the resolved base branch
   with the full assembled body, and leaves the worktree and branch in
   place for review follow-ups.
7. The developer has a real, evidence-backed, reviewable PR — with nothing
   about it that was hand-assembled the way `#53`'s was.

No step of this journey changes shape from what `PRODUCT.md` already
committed to; this story is the first thing that actually walks it past
where `/build` leaves off.

## Out of scope

- **Producing NOTES stubs.** That's `/build`'s own gap (no code path in
  the shipped M4 `skills/build/SKILL.md` writes one). This story defines
  `/finish`'s read side of that contract only; it does not retrofit
  `/build` to produce them. Flagged here, not silently assumed fixed.
- **Backfilling missing evidence.** An item with no evidence folder is
  named in the PR body, not captured fresh by `/finish` calling
  `evidence-capture` on its own initiative — that would blur "verify
  independently, as produced" into "verify whenever `/finish` gets around
  to it," and risks exactly the stale-artifact class of bug this design's
  freshness hold exists to catch. Producing missing evidence is the
  human's (or a re-run `/build` task's) job.
- **`/plan`'s actual `## Not-here follow-ups` heading-level fix** (issue
  #23) — `/finish` reads whatever heading `PLAN.md` currently uses; fixing
  the format itself is `/plan`'s (M3) job, not this story's.
- **Replay-bundle persistence** (issue #34) — a named downstream consumer
  of this story's evidence files, explicitly scoped to its own future
  story. This design doesn't add replay-bundle fields to any manifest.
- **Auto-resolving an ambiguous base branch by guessing** — `/finish` asks
  once rather than defaulting silently to `main` or the worktree's
  upstream if that's not confidently the intended target (see Open
  questions).
- **Fan-out, multi-repo, or concurrent `/finish` runs** — carried forward
  unchanged from `/build`'s own scoping; one sequential run against one
  branch is the only shape this design covers.
- **A GitHub Actions / CI-triggered `/finish`** — this is a human-invoked,
  interactive skill (every step but Step 1's freshness re-check ends in a
  human decision); running it unattended is out of scope.
- **Re-opening or editing a PR `/finish` already created** — `PR`'s verdict
  covers opening one; iterating on review feedback afterward is ordinary
  development on the still-live branch, not a `/finish` concern.

## Alternatives considered

1. **Re-derive evidence freshness against the branch's current `HEAD`** at
   `/finish`-invocation time, instead of each folder's own recorded
   commit. Rejected: this is exactly issue #44's bug shape reproduced one
   layer up (see Step 1) — a floor that keeps moving forward past when
   most artifacts were captured makes the check structurally unpassable
   for everything but the most recent task.
2. **A single batch confirm ("file all N follow-ups: y/n?")** instead of
   per-item accept/edit/skip in Step 3. Rejected: forces an all-or-nothing
   choice on a set that's rarely uniformly good or uniformly skippable —
   either a weak draft rides along to get a strong one filed, or a strong
   one is blocked by a weak one. Per-item costs one more decision per
   follow-up, which is the point: each earns its own issue on its own
   merits, matching "recommend one action; the human decides" applied at
   item granularity rather than batch granularity.
3. **Let a confirmed decision-patch proposal actually get written**, the
   same confirm-then-apply shape Steps 2 and 3 use. Rejected: `PRODUCT.md`
   and the handoff both state "propose; never apply" for this specific
   step, worded identically twice — treating it the same as the other two
   steps would silently soften a distinction the source material draws on
   purpose. This project's context docs are also the thing `/gate-audit`
   and every future `/deep-review` run trust as ground truth; letting an
   automated flow (even a confirmed one) edit them without a human's own
   hands on the file is a materially bigger blast radius than a `CLAUDE.md`
   harvest patch or a new tracked issue, both of which are reversible in
   ways a context-doc drift is not.
4. **Skip the freshness hold entirely** and trust `evidence-capture`'s
   capture-time check as sufficient forever. Rejected: `evidence-capture`
   only ever knew what `HEAD` was *at capture time* — it cannot see a
   later rebase, a REPLAN's hand-revision, or a stray touch on an artifact
   file that happens after capture. A hold that only ever ran once, weeks
   before the PR is actually opened, is not the same guarantee as one that
   re-confirms right before the evidence is published.

## Operational readiness

`skills/finish/SKILL.md` is a prompt file read by a Claude Code session,
plus two small new scripts; no deployed service, no data migration.

- **Rollout**: replaces the M1 stub's frontmatter/body in place, same
  pattern as `build-skill`'s own rollout. No feature flag, no staged
  rollout.
- **Rollback**: `git revert` the commit that replaces the stub; the reused
  scripts (`evidence-capture`, `worktree-setup`, `verify`, `status-flip`)
  are unaffected since this story doesn't modify their contracts.
- **Failure visibility**: every step that can fail reports why and stops,
  rather than degrading silently mid-step — a failed freshness hold names
  the task; a `gh issue create` failure (auth, rate limit) is surfaced per
  item, not swallowed into "follow-ups filed" when some weren't; a `gh pr
  create` failure leaves the branch/worktree exactly as `KEEP` would, so
  no work is lost to a failed network call. `/finish` produces no metrics
  dashboard of its own — its own dated report (Step 5) *is* the
  observability artifact, the same role studious's dated review reports
  already play for that plugin's own health loop.
- **A known, accepted limitation, carried from the handoff's own decisions
  log (decision 7), not new to this design**: raw-URL image links pin to a
  commit SHA. For `MERGE` (a real merge, not a squash), that commit stays
  reachable from the target branch forever, so the link never breaks. For
  `PR`, if the human later squash-merges via GitHub's own UI (common
  default) and deletes the source branch, the original per-commit history
  — and the image blob the raw URL points at — eventually becomes
  unreachable and is a GC candidate. The handoff rules this an accepted
  trade-off ("keeping is the simple honest policy... files are small")
  rather than something to solve by, e.g., also copying evidence into the
  target branch (which would bloat `main` with per-feature evidence and
  contradict "disposable scaffolding"). This design doesn't attempt to
  close that gap; it's named here so a future reader doesn't mistake a
  since-broken raw-URL link for a `/finish` bug rather than a known,
  ratified cost of the squash-merge path specifically.
- **Required demonstration** (this story's own acceptance criteria: "end
  to end against a real BUILT branch"): this project currently has **zero**
  committed content anywhere under `docs/jig/evidence/` in its git history
  — the two live M4 demonstrations used a scratch path outside the
  worktree to route around issue #45, and never actually exercised a
  committed, freshness-held evidence folder. The build phase for this
  story therefore needs a genuine, fresh `/build` run that reaches `BUILT`
  with real evidence folders committed on the branch (not a scratch
  workaround) before `/finish` has anything real to promote — this is the
  first natural end-to-end exercise of `evidence-capture`'s freshness
  guarantee this project will have actually run.

## Open questions

- **Base-branch resolution for `MERGE`/`PR`.** `worktree-setup`'s `--base`
  argument names the branch a worktree was created from, but nothing
  currently persists that value anywhere `/finish` could read it back from
  cold (it's not written into `PLAN.md`, a manifest, or git config). This
  doc commits to the behavior (resolve if possible, ask once if not) but
  not the mechanism — whether that's a `git merge-base` heuristic across
  candidate branches, a new field `worktree-setup` should start recording,
  or always asking. A build-phase decision.
- **What "promoted elsewhere" means for the design-doc/PLAN.md cleanup
  commit on `MERGE`/`KEEP`/`DISCARD`** (no PR body exists to point to,
  unlike `PR`). This doc assumes the evidence table content still gets
  assembled and shown to the human even without opening a PR (so nothing
  is lost), but doesn't fix where that assembled text lives when there's
  no PR to hold it — printed to the session only, or written into the
  dated report from Step 5 as its full body rather than a summary. Likely
  the latter, but not fixed here.
- **cctx's `--latest` ambiguity.** `cctx autopsy --latest` reports on
  whichever Claude Code session was most recently active in this project
  directory — in the common flow (the coach sequencing `/build` then
  `/finish`, §5.5) that's naturally the `/build` session just finished, but
  if a human runs `/finish` in a fresh session days later, `--latest` picks
  up `/finish`'s *own* session instead, which never did the risky work.
  This is inherent to cctx's own documented contract (no session-ID
  hand-off flag exists today) — not something this design can fix from
  jig's side without a cctx feature request, so it's named rather than
  silently assumed accurate in every invocation shape.
- **Exact schema for the two new scripts** (the freshness re-validator and
  the report writer) — argument names, exit codes, output format. Left to
  the build phase per this contract's non-requirements; `evidence-capture`
  and `verify`'s existing argument conventions (`--repo`, `--out`, plain
  exit-code semantics) are the natural precedent to match.
- **Whether a NOTES-stub producer is worth a fast-follow issue on
  `/build`** now that `/finish`'s consumption side is designed and finds
  nothing to consume. Not resolved here — filing that issue is exactly the
  kind of judgment call this story's own Step 3 exists to gate behind a
  human, not something the design doc should pre-empt by filing it itself.
