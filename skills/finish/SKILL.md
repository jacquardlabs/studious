---
name: finish
description: Closes out a BUILT branch — an assembled PR evidence table (Done-means item -> verification method -> evidence link -> pass), a cctx session-cost footer with a preview-only harvest offer, per-item-confirmed follow-up filing, proposed (never auto-applied) PRODUCT.md/DESIGN.md/CLAUDE.md decision patches, a dated build report, and MERGE | PR | KEEP | DISCARD verdict + cleanup. Use when the user says /finish, or a /build session has already reported BUILT (and, if studious is installed, /gate-audit and /gate-acceptance have already passed) and the branch is ready to close out. Never invents evidence, never files an issue or applies a harvest without explicit per-item confirmation in the same turn, and never writes a decision patch to a context doc itself.
---

# /finish

You are the session that closes out a `BUILT` branch. `/build` produces the
branch; studious's `/gate-audit` and `/gate-acceptance` (if installed) judge
it; `/finish` is what turns a judged-ready branch into an evidence-backed
PR (or a merge, a kept branch, or a discard) and leaves nothing about that
branch that a human had to hand-assemble.

**Precondition.** `/finish` runs after a `/build` session reports `BUILT`
— and, if studious is installed, after `/gate-audit`/`/gate-acceptance`
have already passed on this branch. `/finish` never checks for a recorded
gate verdict itself — that would require reading studious's own gate-ledger
state, a sibling-plugin coupling this project doesn't ask for. It assumes
the human invoked it because the branch is ready, the same trust boundary
`/build`'s own `BUILT` → "run `/gate-audit` next" hand-off already relies
on.

Six steps, in order. Steps 1 and 5 are mechanical (scripts decide); Steps
2–4 always end on an explicit human decision in the same turn; Step 6
reports one verdict and performs the matching cleanup once the human names
it.

## Step 1 — PR evidence table

For each task in `PLAN.md` (now fully status-flipped), read its `Done
means` items and the evidence folder `/build`'s own `evidence-capture` call
wrote for it: `docs/jig/evidence/<date>-<task>/`, carrying a
`manifest.json` (`commit_sha`, `commit_timestamp`, one entry per captured
artifact) and the captured artifacts themselves — including the task's
`verify:results` artifact, whose own JSON carries each item's `id`, `kind`,
`tier`, `status`, and `detail`.

**Freshness hold — run this before promoting anything.** Call
`scripts/evidence-freshness --repo <worktree> --evidence <folder>` once per
evidence folder involved (repeat `--evidence` per folder, or one call
covering all of them). This re-validates each folder against its own
recorded `manifest.json` — never against the branch's current `HEAD`.
Re-deriving freshness against current `HEAD` reproduces issue #44's bug
shape one layer up: a producing step that commits *after* writing the
artifact it's timestamping against makes a "must be >= current HEAD" check
structurally unpassable for every folder but the most recent one. The
floor for each folder is that folder's own `manifest.json` — not the
branch's current `HEAD`. `evidence-freshness` re-confirms two narrower,
purely mechanical things:

1. The manifest's `commit_sha` is still an ancestor of the branch's current
   `HEAD` (not a since-rewritten or orphaned commit — a real risk after a
   REPLAN's hand-revision and rebuild).
2. Every artifact file's own mtime is still >= that same recorded
   `commit_timestamp` (catches an artifact silently touched or replaced
   after capture).

**A folder that fails either check is not promoted silently.** Stop before
assembling the PR body. Report the exact task and reason (stale/orphaned)
by name. The human's resume action is re-running the task's evidence
capture (via `/build` or by hand) and re-invoking `/finish`. Do not call
`evidence-capture` yourself to backfill a gap — `/finish` does not invent
or re-capture evidence (see Out of scope in the design doc this skill
implements).

**Any `Done means` item with no corresponding evidence folder at all** (a
task that reached `PASS` by a path other than `/build`'s own loop, e.g. a
hand-verified fix) is named explicitly in the PR body as "evidence not
found for item N" — never silently omitted, never fabricated.

**Assembling the table.** One row per item: item text (from `PLAN.md`'s own
numbered `Done means` line) → verification method (the item's own tier —
`script` / `test-backed` / `probe`) → evidence link → pass (the item's own
`status` from `verify:results`, transcribed, never re-judged).

Two evidence shapes, two treatments:

- **Text evidence** (a `script`/`test-backed` item's `detail` field —
  command, exit code, stdout/stderr, already sitting in the captured
  `verify:results` artifact) is quoted **inline**, in a collapsible
  `<details>` block per item, directly in the PR body. Never written to a
  new repository file.
- **Image evidence** (a `probe` item whose artifact is a screenshot or
  other binary) stays exactly where `evidence-capture` already put it —
  `docs/jig/evidence/<date>-<task>/<label>.<ext>` — and is referenced by
  its raw URL: `https://raw.githubusercontent.com/<owner>/<repo>/<sha>/<path>`,
  because `gh` cannot upload an image into a PR body. Resolve `<owner>/<repo>`
  from the repo's own `origin` remote. Anchor `<sha>` to the commit current
  at the moment this step assembles the table (`git rev-parse HEAD` in the
  worktree) — a real, immutable commit SHA, never the branch name, which
  floats and disappears once the branch is deleted. A squash-merged-then-
  deleted branch can eventually make that raw URL a GC candidate — a known,
  accepted trade-off of keeping evidence in place; don't try to close that
  gap here.

## Step 2 — cctx footer

Gate everything in this step on `command -v cctx` (or the equivalent
existence check).

**Not installed:** state so explicitly in your own output — "cctx not
installed; skipping the session-cost footer and harvest offer" plus the
one-line install pointer (`pipx install cctx-cli`) — and move directly to
Step 3. No error, no stack trace, no silent gap in the PR body where the
footer would have been. Every degradation without a sibling plugin
installed is graceful; none is silent. This project's own current
environment (cctx is not installed here) is this step's most-exercised
path.

**Installed:** run `cctx autopsy --latest` (unmodified — cctx's own
documented contract, no jig-specific flags invented) and append its
findings summary (verdict, findings, session cost) to the PR body as a
distinct footer section, separate from the evidence table. Then offer
`cctx harvest` **interactively**: run it in **preview mode only** — never
pass `--apply` as part of this default flow — show the proposed
`CLAUDE.md` diff, and stop. Only pass `--apply` after the human's own
explicit confirmation, typed in that same turn. Never infer that
confirmation from anything else (a prior "yes" to a different question, an
inferred preference, silence). This matches cctx's own CLI contract exactly
(`cctx harvest` previews and confirms by default; `--apply` is the caller's
opt-in to skip that prompt) and the acceptance criteria's own wording:
always preview-confirms, never auto-applies.

## Step 3 — File survivors

Two follow-up sources, both drafted earlier in the pipeline, neither filed
until now:

- **Not-here follow-ups** — `PLAN.md`'s own `## Not-here follow-ups`
  section (bulleted, one line each). Read it directly. The `##` level is
  confirmed safe, not just carried forward (story `plan-skill`, issue #23):
  `docs/design/plan-skill.md`'s Step 6 re-verified this against the
  actually-installed viva, including the `Revision History`-collision case
  a bare heading-level read would miss — `/plan`'s own viva invocation
  passes an explicit `--split-on` rather than relying on auto-detect alone.
- **NOTES stubs** — an executor's stray discoveries during a task ("outside
  Done-means... never into the diff") are meant to land in a NOTES stub
  rather than the diff. `/build`'s current implementation does not yet
  write these (no NOTES-stub step exists in `skills/build/SKILL.md` today).
  Look for one anyway, and report "0 NOTES stubs found" rather than
  treating their absence as an error — today's real branches file real
  Not-here follow-ups and zero NOTES-derived issues, an honest, not a
  broken, result.

For each survivor, draft a GitHub issue (title + body, citing the task and
`PLAN.md` line it came from) and present the **full batch** of drafts to
the human before filing anything. Draft for the per-item scan that follows:
an imperative title under 70 characters, a body of at most 5 lines (what,
why it survived, the citing task and `PLAN.md` line), and the batch
presented as a numbered list the human can accept/edit/skip down in one
pass — never one draft per screen. Confirmation is **per-item**, not
all-or-nothing: the human accepts, edits, or skips each draft individually.
Only `gh issue create` calls for accepted (or accepted-with-edits) drafts
run; a skipped draft is dropped, not saved for a later run. No code path
calls `gh issue create` without that specific item's confirmation having
already happened in this same turn — a batch "file all N? y/n" is exactly
the shape this rejects: it would either force-file a mediocre follow-up to
get a good one filed, or block a good one on a bad one.

If a `gh issue create` call itself fails (auth, rate limit), surface that
failure by name, per item — never fold it silently into "follow-ups filed"
when some weren't.

## Step 4 — Propose decision patches

Design decisions that outlive the feature — a granted pattern exception, a
new contract convention, a ruled fork with lasting consequences — become
proposed diffs against `PRODUCT.md` / `DESIGN.md` / `CLAUDE.md`.

This step is asymmetric with Steps 2 and 3, deliberately: cctx harvest and
issue-filing both *do* write something once the human confirms in-flow.
**Decision patches never do — confirmed or not.** End this step by printing
the proposed diff blocks. Do not call `Edit`, `Write`, `git apply`, or any
other patch mechanism against `PRODUCT.md`, `DESIGN.md`, or `CLAUDE.md` in
this step, under any branch of this flow, even after an explicit "yes."
"Propose; never apply" is this step's whole shape — the human copies the
diff in by hand, or runs it through their own separate process. This is the
same propose-only posture studious's own `/deep-review` reviewers already
take toward these same three context docs.

## Step 5 — Dated build report

Assemble a durable copy of what Steps 1–4 produced — the evidence table,
the cctx footer (or its "not installed" note), which follow-ups were filed
(with their new issue numbers) and which were skipped, and the proposed
decision patches verbatim — into a single markdown file, then call
`scripts/build-report --repo <worktree> --slug <story-slug> --content
<path>` (optionally `--date`; defaults to today, UTC). This writes
`docs/jig/reports/YYYY-MM-DD-<story-slug>-build-report.md` — same class and
naming shape as studious's own dated review reports
(`docs/studious/<kind>-reviews/YYYY-MM-DD-<kind>-review.md`), reusing an
established convention rather than inventing a new report shape.
`build-report` only performs the mechanical write; it never drafts,
summarizes, or judges the content itself — that assembly is this step's own
job, not the script's.

`build-report` does not commit its own write. Commit the new report file
yourself, as its own commit, distinct from Step 6's cleanup commit below —
same "scripts write, the session commits" division `evidence-capture`
already established for `/build`.

`docs/jig/evidence/` and `docs/jig/reports/` are never touched by Step 6's
cleanup — both are kept post-merge; the files are small.

## Step 6 — Verdict + cleanup

Report one of four tokens and perform the matching cleanup:

| Verdict | Meaning | Worktree | Branch | PR |
|---|---|---|---|---|
| `MERGE` | Merge straight into the target branch (no PR) — e.g. a story branch merging into its parent epic branch under studious's own orchestration, or a solo developer merging directly to `main`. | Removed | Deleted after a successful merge | None opened |
| `PR` | Open a GitHub PR carrying the assembled body (evidence table + cctx footer + filed-issue links + report link) as its description. | **Kept** — follow-up commits addressing review feedback still need it | **Kept**, un-merged, tracked by the open PR | `gh pr create` |
| `KEEP` | Preserve the branch and its work without merging or opening a PR — e.g. paused work, or a spike worth keeping for reference. | Kept | Kept | None opened |
| `DISCARD` | Abandon the work outright — e.g. an ESCALATE finding proved the direction wrong, or the branch is superseded. | Removed | Deleted | None opened |

**Ask the human which token applies. Do not pick one.** This table is the
direct answer to "a build/demo that only exercises one verdict path risks
leaving the other three under-specified" — every token gets its own row,
its own worktree/branch/PR handling, and none of the four is the silent
default.

Every verdict shares the same cleanup step *before* whichever git action
happens: remove `docs/design/<story-slug>.md` and `PLAN.md` (and any
scratch `docs/jig/demonstrations/` narrative, if used) in a commit whose
message notes the promoted-elsewhere destination — the PR body, for `PR`;
the dated build report's own full text, for `MERGE`/`KEEP`/`DISCARD` (no PR
body exists to point to on those three, so the report is where the
assembled evidence table actually lives once the design doc is gone).
Design docs and `PLAN.md` are disposable scaffolding; they live on the
branch and die at merge — what survives is the Done-means table + evidence
(the PR body or the report) and any decision patches a human chose to
apply by hand.

`MERGE` and `PR` both require resolving a target/base branch. Resolve it,
cheapest-and-most-confident signal first, rather than guessing silently
toward `main`:

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

## Why this shape

"Recommend one action; the human decides. Propose; never apply" is this
skill's whole shape end to end: Step 3 confirms per-item before any `gh
issue create`; Step 4 never applies regardless of confirmation; Step 6
reports one verdict and waits — it does not pick one. "Nothing signs off
on itself" is why Step 1 re-validates evidence against its own recorded
commit rather than trusting `evidence-capture`'s past word forever, and why
a missing evidence folder is reported, never fabricated. "Standalone-
capable" is Step 2's explicit, named cctx-absent path. "Disposable
scaffolding, durable decisions" is Step 6's cleanup contrasted with Step
5's report and Step 1's evidence retention. "Judgment in the model,
mechanics in scripts" is the freshness hold (`evidence-freshness`) and the
report write (`build-report`) being scripts; the human's per-item
accept/skip and the `MERGE`/`PR`/`KEEP`/`DISCARD` choice are the judgment
calls no script makes.
