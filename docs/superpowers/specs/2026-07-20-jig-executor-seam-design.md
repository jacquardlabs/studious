# Design: Wire jig as a first-class executor across the build seam

**Date:** 2026-07-20
**Status:** Design, pre-implementation
**Story:** jig-executor-seam
**Source:** [#143](https://github.com/jacquardlabs/studious/issues/143)

## Problem & persona

The persona is PRODUCT.md's primary user: a developer building features with Claude
Code who wants product judgment and quality gates woven into the build. `/work-on`'s
build handoff (`commands/work-on.md:95`) hands the how-layer away with "build with your
own workflow" and names Superpowers as the one example. jig ships `/design`, `/plan`,
`/build`, `/finish` — built to fill exactly that slot — but `grep -ri jig commands/
agents/ skills/ reference/` returns zero hits. The arrow is one-directional today: jig
already detects studious and hands off to `/gate-design-review` / `/gate-audit`,
degrading explicitly when studious is absent (`skills/coach/SKILL.md`, `skills/design/
SKILL.md`); studious never hands in. A user with both installed gets no signal from
studious that jig exists, so jig goes unused even when present — the live pain behind
this issue.

The job-to-be-done: at the two points `/work-on` steps back (design, build), tell the
user jig satisfies the contract, exactly as it already does for Superpowers; and when
jig is what actually built the story, get its terminal status back into `/work-on`'s
flow state without asking the user to relay it by hand.

## Proposed design

Two repos, two PRs. No `bin/gate-ledger` changes in either — `work-log`'s `--outcome`
is already free text, and every call already appends to a `.history` array carrying
`{step, outcome, sha, at}`, which is everything the read side below needs.

### 1 · studious — recommend jig at the two handoffs (`commands/work-on.md`)

Add one bullet at piece 2 (design, after the existing Superpowers bullet at line 78)
and one at piece 4 (build, after line 99), same tone and placement as the existing
Superpowers mentions, additive only:

- **Design handoff:** "If jig is installed, note that its `/design` workflow (batch
  interview → drafted doc → viva sign-off) produces a doc satisfying the contract;
  otherwise any hand-written spec does."
- **Build handoff:** "If jig is installed, its `/plan` + `/build` workflow picks up
  from the design doc and reports `BUILT | PAUSED | ESCALATED` back into this work
  file (see 'Find the next piece — evidence first') — the next `/work-on` invocation
  resumes from that without asking; otherwise the user builds however they like."

No new detection mechanism: the existing Superpowers bullet has never had a mechanical
`command -v` check behind it either — it's a prose recommendation the model makes from
its own context, and jig gets the identical treatment. Superpowers detection is
unaffected.

### 2 · studious — read jig's self-reported build status (`commands/work-on.md`)

New bullet in "Find the next piece — evidence first," after the existing "Build
progress" bullet:

> **Executor-reported build status** — an executor satisfying
> `reference/worker-contract.md` may log its own terminal status for the build piece
> without setting `--phase` itself (phase judgment stays this command's call). Read it
> with `gate-ledger work-get --slug "<slug>"`'s `.history`, most recent `step: "build"`
> entry. Trust it only when its `sha` is still HEAD — commits since mean the report is
> stale and the commit-evidence check above wins instead (the same sha-anchoring
> already used for gate verdicts elsewhere in this section). If current: `BUILT`
> corroborates the commit check; `PAUSED` — stay at phase `build`, and say so using the
> reported status rather than a generic "no commits yet"; `ESCALATED` — regress phase
> to `design` and surface the reported reason, the same shape as design-review's
> `RETHINK` → `design` above, mirroring jig's own documented "`/build` ESCALATED routes
> back to `/design`."

### 3 · studious — publish the reporting contract (`reference/worker-contract.md`)

- Line 8-10 gets jig named alongside Superpowers: "a worker MAY use Superpowers'
  plan/execute workflow when it's installed, or jig's `/plan` + `/build` workflow, but
  a worker without either must still satisfy every row below."
- New short section between "What a worker must return" and "Boundaries":

  > ## Status reporting
  >
  > A worker MAY additionally report its own terminal status for the phase it just
  > finished. First resolve which work file is this feature's the same way `/work-on`
  > does it: `gate-ledger work-list`, match the current branch's row. Found → `gate-ledger
  > work-log --slug "<that-slug>" --step <phase> --outcome "<status>"`, omitting
  > `--phase` (the phase judgment stays `/work-on`'s call). No match, or `gate-ledger`
  > not on `PATH` at all → skip silently; this is best-effort corroboration, not a
  > required part of the contract. This is a first-person status report, not a gate
  > verdict or a self-assessment against a rubric, and does not conflict with "workers
  > never... record a verdict" above — jig's `/build` reports `BUILT | PAUSED |
  > ESCALATED` this way when `gate-ledger` is present.

`commands/work-through.md` needs no change — it already refers to workers and
`reference/worker-contract.md` generically, with no Superpowers-specific mention to
mirror.

### 4 · studious — README

One line added to "Works well with" (line 171-172 today), parallel to the existing
Superpowers entry:

> - [jig](https://github.com/jacquardlabs/jig): a purpose-built executor for the build
>   step — `/design`, `/plan`, `/build`, `/finish` satisfy the worker contract directly
>   and report back into the same flow state.

### 5 · jig (separate repo, separate PR) — call the contract from `/build`

Only `skills/build/SKILL.md` changes; `/finish`'s verdict vocabulary (`MERGE | PR |
KEEP | DISCARD`) doesn't map onto any `/work-on` piece, so it's out of scope (narrower
than this issue's original framing, which over-included it).

Right before `/build` reports its final verdict to the user, guarded exactly the way
jig already guards its own `command -v gate-ledger` checks elsewhere (`skills/coach/
SKILL.md`, `skills/design/SKILL.md`):

1. `command -v gate-ledger` — not found → skip silently, report the verdict as today.
2. Found → `gate-ledger work-list`, match a row whose branch column equals the current
   branch. No match → skip silently.
3. Match → `gate-ledger work-log --slug "<slug>" --step build --outcome "<BUILT|PAUSED|ESCALATED>"`
   (no `--phase`), then report the verdict as today.

## Why this shape

- **Recording originates where the fact is known.** Only jig's own `/build` session
  knows its verdict at the moment it happens; `/work-on` runs later, in a different
  turn. Asking `/work-on` to solicit the verdict from the user would satisfy the letter
  of "resumes... instead of asking" by not literally asking about the *step*, but it
  would still require the user to relay jig's output by hand — the issue's stated goal
  is to remove that relay entirely.
- **Phase judgment stays one place.** jig reports status, never phase. `/work-on`
  already owns every other phase transition in the flow (including backward ones —
  design-review's `RETHINK` → `design` is existing precedent); an executor setting its
  own `--phase` would duplicate that judgment in two repos and let them drift.
  ESCALATED regressing to `design` is new precedent this design adds, but it's the same
  shape as the existing RETHINK case, not a novel one.
- **No new gate-ledger surface.** Free-text `--outcome` and the existing `.history`
  array already carry everything both sides need — the smallest change that closes the
  loop, per this project's own bias against unnecessary schema growth.
- **Branch-match discovery, not a threaded slug.** jig could instead be handed the
  work-file slug explicitly in `/work-on`'s build-handoff bullet. Branch-match is
  preferred because `/work-on` already uses the identical convention to resolve "do the
  next piece" for an empty `$ARGUMENTS`, so jig reuses an existing idiom instead of
  studious inventing a new one-off handoff field, and it keeps working even if a jig
  session is invoked directly (without a fresh `/work-on` build handoff having just
  run).

## Out of scope

- Any change to `#150`'s repo-merge proposal — this design assumes the current
  two-repo topology and doesn't depend on that decision either way.
- jig's own `/design` verdict vocabulary (`DESIGNED | NEEDS RESEARCH | REVISED`) is not
  recorded back — the issue's scope names only the build step's verdicts, and the
  design step's evidence check (does the doc file exist) already has what it needs.
- `bin/gate-ledger` code changes — none needed (see above).
- jig's `/finish` — its verdict vocabulary doesn't correspond to any `/work-on` piece.

## Testing

Doc/prompt-only change on both sides; no new executable code path. Verification is
`scripts/check_references.py` and `markdownlint-cli2` on the studious side (existing CI
lanes, unaffected file types, both pass clean), jig's own `pytest tests/` (418 passed,
1 skipped — untouched by this change's scope), and a manual round-trip walkthrough of
the mechanism the design depends on, run before this was called done:

`work-set --branch` from a main checkout, then from a **separate linked git worktree**
on that branch (`git worktree add`, the same primitive jig's own `worktree-setup`
script uses for a `/build` session) — `gate-ledger work-list` found the row by branch
match, `gate-ledger work-log --step build --outcome ESCALATED` (no `--phase`) logged
against it, and `gate-ledger work-get` read back a sha-anchored `.history` entry. This
confirms both load-bearing assumptions this design depends on and lint/tests can't see:
`bin/gate-ledger`'s `.studious/` root-anchoring (`repo_root()` via `git rev-parse
--git-common-dir`) already unifies state across linked worktrees of the same repo, and
branch-match discovery resolves correctly from inside one. Test artifacts (worktree,
branch, work file) were removed after.
