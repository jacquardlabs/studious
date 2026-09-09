---
name: ship
description: Closes out a BUILT branch — an assembled PR evidence table (Done-means item -> verification method -> evidence link -> pass), a cctx session-cost footer with a preview-only harvest offer, per-item-confirmed follow-up filing, proposed (never auto-applied) PRODUCT.md/DESIGN.md/CLAUDE.md decision patches, a dated build report, and MERGE | PR | KEEP | DISCARD verdict + cleanup. Use when the user says /ship, or a /build session has already reported BUILT (with /review already passed) and the branch is ready to close out. `/ship --handback` is the PR-less variant a dispatched worker uses to return its branch — manifest and summary only, no episode, no PR. Never invents evidence, never files an issue or applies a harvest without explicit per-item confirmation in the same turn, and never writes a decision patch to a context doc itself.
---

# /ship

You are the session that closes out a `BUILT` branch. `/build` produces the
branch; studious's `/review` (if installed) judges
it; `/ship` turns a judged-ready branch into an evidence-backed PR (or a
merge, a kept branch, or a discard) with nothing left to hand-assemble.

**Precondition.** `/ship` runs after a `/build` session reports `BUILT` and
after `/review` has passed on this branch. `/ship`
never checks for a recorded gate verdict itself — gates are skippable by
design, and the gate ledger is per-branch flow state a human can
legitimately have bypassed. It trusts the human invoked it because the
branch is ready, same as `/build`'s own `BUILT` → "run `/review` next"
hand-off.

## Two modes

- **`/ship`** — the full closeout below: evidence table, cost footer, follow-ups,
  decision patches, dated report, and one of `MERGE` / `PR` / `KEEP` / `DISCARD`.
- **`/ship --handback`** — the worker's PR-less return. A dispatched executor finishing
  its story hands the branch back with a manifest and a summary and nothing else: no
  episode is convened, no PR is opened, no verdict is recorded. Follow
  `reference/handback-contract.md`, which carries that procedure in full; consult it,
  don't restate it here, and don't run any of the six steps below on this path.

Convening is not judging: `/ship` convenes no episode and never writes a verdict — the
work episode `/build` convened is the delivery check.

Six steps, in order. Steps 1 and 5 are mechanical (scripts decide); Steps
2–4 always end on an explicit human decision in the same turn; Step 6
reports one verdict and performs the matching cleanup once the human names
it.

## Step 1 — PR evidence table

**`<worktree>` wherever it appears in this skill** is the checkout the build ran
in — the path `git rev-parse --show-toplevel` prints *there*. Resolve it once,
here, and pass it explicitly to every command below that takes it. None of those
flags may be left to default: `--repo` defaults to `.`, so a session whose own
cwd is some other checkout would read that repository and report its state as
this feature's — an evidence table assembled, plausibly, off the wrong branch.

The table is assembled by a script, never by hand (#249, #421):

```
studious ship-body --plan <worktree>/PLAN.md --repo <worktree> --branch "$(git -C <worktree> rev-parse --abbrev-ref HEAD)" --out <scratch-path>/body.md
```

`--branch` takes that exact command, not `git branch --show-current`: capture
stamped the manifest using `rev-parse --abbrev-ref HEAD` (`scripts/_gitutil.py`'s
`current_branch`), literal `HEAD` fallback included — `--show-current` prints an
empty string on a detached checkout that matches no manifest.

What it does, so you can read its output: for every task in `PLAN.md` (now fully
status-flipped) it asks `evidence-capture resolve` which folder in the local,
gitignored store (`.studious/build-evidence/<date>-<task>-<branch-slug>/`, the main
checkout's, worktree-shared) holds the task's captured artifacts — never rebuilding
the path from its shape:
rebuilding `.studious/build-evidence/<date>-<task>/` matches nothing. <!-- evidence-grammar: counterexample -->
It resolves `--task exorcise` the same way — `/build` Step 3 captures the exorcise
report under that id (`exorcist:report`, pinned in `reference/evidence-format.md`); no
folder means no pass landed, so no row, no remark. Then it runs the **freshness hold**
(`evidence-freshness`) over every folder it found, against each folder's own
`manifest.json` — never against the branch's current `HEAD` (issue #44's shape one
layer up) — and only then renders:

- one row per `Done means` item: item text → tier → evidence → the item's own `status`
  from `verify:results`, transcribed, never re-judged. Text evidence is quoted
  **inline**, in a collapsible `<details>` block per item; image evidence names the
  local path — `image evidence at <path> (local store — attach to the PR if a
  reviewer needs it)` — and never fabricates a URL for a file no remote holds;
- a load-bearing task's Inspector report, verdict line first, in that task's block;
- the exorcise block: the report's `Concepts removed:` line (and its `Concepts kept:`
  clause when present) and its `## Held` section verbatim — the route `/build` Step 3
  promises a `hold` finding;
- the plan's `## Amendments` and the viva sign-off's `### Decisions` blocks verbatim —
  the two records that would otherwise die with `PLAN.md`.

Three states it renders instead of asking you: a **legacy** folder (records no
branch) is promoted with its caveat in the cell; a task with **no folder** reads
`evidence not found for item N` — named, never silently omitted; a **stale or
orphaned** folder, or an **ambiguous** one (several branch-less candidates), is a
**stop**: exit 1, the task and reason named on stderr, nothing written. On a stop,
report it verbatim and end here. The resume action is the human's: re-run the task's
capture (via `/build` or by hand) for a stale folder, or read the candidates'
manifests for an ambiguous one. Do not call `evidence-capture` yourself to backfill
a gap — `/ship` does not invent or re-capture evidence.

`<scratch-path>/body.md` is the PR body's first section. Steps 2–4 append to it.

## Step 2 — cctx footer

Gate everything in this step on `command -v cctx` (or the equivalent
existence check).

**Not installed:** state so explicitly in your own output — "cctx not
installed; skipping the session-cost footer and harvest offer" plus the
one-line install pointer (`pipx install cctx-cli`) — and move directly to
Step 3. No error, no stack trace, no silent gap in the PR body.

**Installed:** run `cctx autopsy --latest` (unmodified — no flags of our own
invented) and append its findings summary (verdict, findings, session cost)
to the PR body as a distinct footer section, separate from the evidence
table. Then offer `cctx harvest` **interactively**: run it in **preview mode
only** — never pass `--apply` as part of this default flow — show the proposed
`CLAUDE.md` diff, and stop. Only pass `--apply` after the human's own
explicit confirmation, typed in that same turn; never infer confirmation
from anything else (a prior "yes" to a different question, an inferred
preference, silence). This matches cctx's own CLI contract (`cctx harvest`
always preview-confirms, never auto-applies; `--apply` skips that prompt).

## Step 3 — File survivors

Two follow-up sources, both drafted earlier in the pipeline, neither filed
until now:

- **Not-here follow-ups** — `PLAN.md`'s own `## Not-here follow-ups` section
  (bulleted, one line each). Read it directly. The `##` level is confirmed
  safe against the actually-installed viva (story `plan-skill`, issue #23),
  including the `Revision History`-collision case a bare heading-level read
  would miss — `/build`'s own viva invocation passes an explicit `--split-on`
  rather than relying on auto-detect alone.
- **NOTES stubs** — an executor's stray discoveries during a task ("outside
  Done-means... never into the diff") belong in a NOTES stub rather than the
  diff. `/build` doesn't write these yet (no NOTES-stub step in
  `skills/build/SKILL.md` today). Look for one anyway and report "0 NOTES
  stubs found" rather than treating absence as an error.

For each survivor, draft a GitHub issue (title + body, citing the task and
`PLAN.md` line it came from) and present the **full batch** of drafts to the
human before filing anything: an imperative title under 70 characters, a
body of at most 5 lines (what, why it survived, the citing task and
`PLAN.md` line), presented as a numbered list the human can accept/edit/skip
down in one pass — never one draft per screen. Confirmation is **per-item**,
not all-or-nothing: Only `gh issue create` calls for accepted (or accepted-with-edits) drafts
run; a skipped draft is dropped, not saved for a later run. No code path
calls `gh issue create` without that specific item's confirmation. A batch
"file all N? y/n" is rejected — it would either force-file a mediocre
follow-up to get a good one filed, or block a good one on a bad one.

If a `gh issue create` call itself fails (auth, rate limit), surface that
failure by name, per item — never fold it silently into "follow-ups filed"
when some weren't.

## Step 4 — Propose decision patches

Design decisions that outlive the feature — a granted pattern exception, a
new contract convention, a ruled fork with lasting consequences — become
proposed diffs against `PRODUCT.md` / `DESIGN.md` / `CLAUDE.md`.

Unlike Steps 2 and 3 (cctx harvest and issue-filing both *do* write once the
human confirms in-flow), **Decision patches never do — confirmed or not.**
End this step by printing the proposed diff blocks. Do not call `Edit`,
`Write`, `git apply`, or any other patch mechanism against `PRODUCT.md`,
`DESIGN.md`, or `CLAUDE.md` in this step, under any branch of this flow, even
after an explicit "yes." Propose; never apply — the human copies the diff in
by hand or runs it through their own process. Same propose-only posture
studious's `/health` lanes already take toward these three docs.

## Step 5 — Dated build report (only when no PR body will exist)

**This step is conditional on Step 6's verdict, so resolve that first when the
answer is already known, or come back to this step after Step 6 names it.** On
the `PR` verdict, skip this step entirely: the PR body carries everything
Steps 1–4 produced, and a committed copy would be duplicate review noise.

On `MERGE`, `KEEP`, or `DISCARD` — no PR body exists — the report IS the
durable record. Assemble what Steps 1–4 produced — `ship-body`'s output, the
cctx footer (or its "not installed" note), which follow-ups were filed (with
issue numbers) and which were skipped, and the proposed decision patches
verbatim — into a single markdown file, then call
`studious build-report --repo <worktree> --slug <story-slug> --content
<path>` (optionally `--date`; defaults to today, UTC). This writes
`docs/studious/build-reports/YYYY-MM-DD-<story-slug>-build-report.md` — same
class and naming as studious's own dated review reports. `build-report` only
performs the mechanical write; the assembly is this step's job, not the
script's.

`build-report` does not commit its own write. Commit the new report file
yourself, as its own commit, distinct from Step 6's cleanup commit below.

Evidence needs no handling either way: the store is local and gitignored
(`.studious/build-evidence/`), never committed, so there is nothing for Step
6's cleanup to touch — the folders simply stay on the user's disk. Reports,
when written, are kept post-merge; they are the only surviving copy for the
three PR-less verdicts.

## Step 6 — Verdict + cleanup

Report one of four tokens and perform the matching cleanup:

| Verdict | Meaning | Worktree | Branch | PR |
|---|---|---|---|---|
| `MERGE` | Merge straight into the target branch (no PR) — e.g. a story branch merging into its parent epic branch under studious's own orchestration, or a solo developer merging directly to `main`. | Removed | Deleted after a successful merge | None opened |
| `PR` | Open a GitHub PR carrying the assembled body (evidence table + cctx footer + filed-issue links + report link) as its description. | **Kept** — follow-up commits addressing review feedback still need it | **Kept**, un-merged, tracked by the open PR | `gh pr create` |
| `KEEP` | Preserve the branch and its work without merging or opening a PR — e.g. paused work, or a spike worth keeping for reference. | Kept | Kept | None opened |
| `DISCARD` | Abandon the work outright — e.g. an ESCALATE finding proved the direction wrong, or the branch is superseded. | Removed | Deleted | None opened |

**Ask the human which token applies. Do not pick one.** Every token gets its
own row, its own worktree/branch/PR handling, and none of the four is the
silent default.

Every verdict shares the same cleanup step *before* whichever git action
happens: remove `docs/design/<story-slug>.md`, its `docs/design/<story-slug>-premortem.md`,
and `PLAN.md` (and any scratch `docs/design/demonstrations/` narrative, if used). A project that gitignores
them the way this plugin does has nothing to commit — delete them from the
worktree and say so. A project that tracks them needs a `git rm` commit whose
message notes the promoted-elsewhere destination. Check which case you are in
(`git ls-files -- <path>`) rather than assuming; the destination is the PR
body for `PR`, the dated build report's full text for
`MERGE`/`KEEP`/`DISCARD` (no PR body exists on those three). Design docs and
`PLAN.md` are disposable scaffolding that die at merge; what survives is the
Done-means table + evidence (the PR body or the report) and any decision
patches a human chose to apply by hand.

`MERGE` and `PR` both require resolving a target/base branch. Resolve it
cheapest-and-most-confident signal first — never guess silently toward
`main`:

1. If the current branch name follows the `<parent>--<story-slug>`
   convention (a literal `--` separator) and a local branch matching the
   prefix before the last `--` exists, that parent branch is the target —
   the common case for a studious-orchestrated story worktree.
2. Otherwise, if the branch has an upstream/tracking branch configured
   (`git rev-parse --abbrev-ref --symbolic-full-name @{u}`) and it isn't
   the same branch, use it.
3. Otherwise, if exactly one well-known default branch exists in the repo
   (`main` or `master`) and the current branch demonstrably diverged from
   it, use it.
4. If none of the above resolves with confidence — more than one candidate
   applies, or none do — **ask the human once, by name**, before acting.
   Never default silently to `main` or to the worktree's upstream if that
   isn't confidently the intended target.
