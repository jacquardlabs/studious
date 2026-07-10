# Commit gate-emitted docs before recording their verdict

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Source:** [#99](https://github.com/jacquardlabs/studious/issues/99), story
`gate-doc-commit-ordering` of epic `gate-ledger-robustness` (M2)

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features
with Claude Code who wants product judgment and quality gates woven into the build,
without heavy process."** This persona trusts the PR-time hook
(`hooks/gate-reminder.sh`, backed by `bin/gate-ledger`'s `cmd_status`) to tell them,
truthfully, whether a gate's verdict still reflects the branch as it stands — that
trust is the entire point of recording verdicts at all instead of re-litigating them
by eye. PRODUCT.md's secondary persona, **"the maintainer dogfooding Studious on
Studious,"** is who actually hit this: issue #99 was filed from a `/work-through` dry
run against this repo's own epic flow.

The mechanism, read directly from `bin/gate-ledger`:

- `cmd_record` (`gate-ledger record --gate G --verdict V`) stamps
  `sha: $(head_sha)` — `git rev-parse --short HEAD` **at the moment `record` runs.**
- `cmd_status`, which both the PR-time hook and the epic finale's "ready" check read,
  compares that stored sha against current HEAD: if they differ, it reports `"$gate
  ran $n commit(s) ago — re-run before merging"` regardless of how trivial the
  intervening commit was.

So the instant a gate's own workflow writes a file to disk *after* `gate-ledger
record` already ran — even one more commit, even a doc the gate itself produced —
every later reader of that verdict sees it as stale, whether or not anything
substantive changed. Issue #99, verbatim: "the finale acceptance agent committed its
register doc *after* recording SHIP, leaving both gate verdicts 1 commit stale at
`ready` — the PR-time hook then asks 're-run before merging?' on an epic that just
passed everything."

Two instances of the same gap, one prescribed by a command's own text and one
observed in practice:

1. **Prescribed, in `commands/gate-design-review.md`.** Part 3 ("Persist the
   register") instructs writing `docs/studious/premortems/<slug>.md` on `PROCEED TO
   PLAN`. A separate, later "Record the verdict" section runs `gate-ledger record`.
   Nothing between the two tells the agent to commit the register first — an
   ordinary run can record the verdict against HEAD and only commit the register
   (along with whatever else it hands back) afterward.
2. **Observed, via `commands/gate-acceptance.md` run as the epic finale.** This
   command's own text has no explicit doc-write step today — Part 2 only *reads* an
   existing pre-mortem register, never writes one. Yet #99's dry run caught exactly
   this failure mode on the acceptance gate: dispatched as the finale
   (`workflows/epic-driver.js`), the agent executing `gate-acceptance.md`'s workflow
   produced and committed doc-shaped output ("reconciliation notes," #99's own term
   for it) *after* already recording `SHIP`. Nothing in the command asked it to write
   that note — synthesizing an acceptance verdict across an entire epic's stories is
   more involved than reviewing one branch, and an agent with `Write` access doing
   that synthesis can organically produce and commit something the prompt never
   named. The ordering rule can't cover only the prescribed write; it has to cover
   whatever a gate run commits, prescribed or not.

Fail-safe today, per #99: `cmd_status` only *over*-warns (asks for a redundant
re-run) — it never silently skips a re-run that's actually needed, because a
genuinely stale sha (more than the gate's own tidy-up commit) still triggers the same
message. This is noise, not a correctness bug: a maintainer who sees "re-run before
merging" on an epic that just passed every gate learns to distrust the hook, which
erodes the exact signal PRODUCT.md's "gates are lightweight and optional" trust model
depends on.

## Proposed design

State one ordering rule, in substance the same sentence, in the three places named by
the acceptance criteria — no new mechanism, no change to what gets recorded:

> **Before running `gate-ledger record`, commit every file this gate's run wrote or
> modified — a prescribed artifact like the pre-mortem register, or anything the
> agent produced on its own initiative while doing the review. The verdict's recorded
> sha must be the same commit a reader lands on at HEAD.**

This is a pure instruction insertion immediately ahead of the existing
`gate-ledger record` step in each location — **no change to any gate's verdict
tokens or decision logic**, per the acceptance criteria. "Code owns bookkeeping;
prompts own judgment" stays intact: `bin/gate-ledger`'s `cmd_record`/`cmd_status`
code is untouched; the fix is entirely in what the prompt tells the agent to do
*before* it calls that code.

The three locations, and why each one needs its own statement rather than one file
being enough:

- **`commands/gate-design-review.md`** — add the rule where "Record the verdict"
  already sits, pointing at the register Part 3 may have just written. This is the
  prescribed-write case.
- **`commands/gate-acceptance.md`** — add the same rule, phrased generally rather
  than naming a specific artifact (there is none prescribed here today): commit
  whatever this run produced, then record. This covers the emergent-write case #99
  actually observed.
- **`workflows/epic-driver.js`'s finale acceptance dispatch** — a reader might
  reasonably ask why this needs its own copy of the rule when the dispatched agent
  is already told to "execute [the command]'s workflow," which will carry the rule
  once the command file is fixed. The answer: the driver's prompt doesn't stop at
  that pointer. It appends its own separate, literal, directly-executable
  instruction — `Record from inside the epic worktree: cd "${epicWorktree}" &&
  gate-ledger record --gate acceptance --verdict "<TOKEN>"` — which an agent can run
  exactly as given without re-deriving "and commit first" from the referenced
  markdown. The driver's own text is the last thing the agent reads before acting,
  so it's also the text that has to carry the rule, not only the file it points at.

Where exactly the sentence lands in each file (a new one-line subsection vs. folded
into the existing paragraph) is a build-phase detail — see Open questions.

## User journey

Extends PRODUCT.md's critical user journey #2 ("Per-feature gate flow": `/gate-design-review` > build > `/gate-audit` > `/gate-acceptance` > merge) to epic scope via `/work-through`'s finale, per CUJ #2's own epic-scale entrypoint.

1. The persona runs `/gate-design-review` on a design doc. Verdict comes back
   `PROCEED TO PLAN`. **Changed:** before recording that verdict, the agent commits
   the pre-mortem register it just wrote — the recorded sha now points at a commit
   where the register genuinely exists.
2. Later, the epic reaches its finale. The acceptance gate runs against the whole
   epic. **Changed:** whatever the agent wrote in the course of that review — a
   deliberate artifact or a note it produced synthesizing several stories' worth of
   evidence — gets committed before `gate-ledger record --gate acceptance --verdict
   SHIP` runs.
3. All gates proceed; the finale marks the epic `ready`
   (`workflows/epic-driver.js`'s existing ready-check, untouched by this story).
4. The persona runs `gh pr create`. `hooks/gate-reminder.sh` reads the ledger,
   compares recorded shas against HEAD, and finds them equal — no spurious "re-run
   before merging" on a branch that has nothing left to re-run.
5. **Must not regress:** a gate that genuinely needs re-running (real code or design
   changes landed after the verdict) still shows a real, non-zero commit gap and
   still triggers the hook's warning — this story changes only the ordering of a
   commit relative to a record call, never what `cmd_status` considers stale.

## Out of scope

- **The per-story `gatePrompt()` dispatch** (`workflows/epic-driver.js`, the function
  used for per-story design-review and acceptance gates, distinct from the finale
  prompts). It embeds the identical structural gap — its own appended, literal
  `cd "${storyWorktree(story)}" && gate-ledger record ...` line, separate from
  whatever the referenced command file says — and, via `gate-design-review.md`, the
  same pre-mortem-register write exposure the finale acceptance dispatch has. The
  acceptance criteria names "the finale prompts" specifically, not the per-story
  ones; this story doesn't touch that path. Flagged here, not silently dropped —
  worth a follow-up look once the command-file fix lands, since the same fix may or
  may not already suffice there (see Open questions).
- **The finale audit-compile dispatch and the finale pre-mortem-verification
  dispatch** (`finaleAuditRound` and the `premortem-auditor` call in
  `workflows/epic-driver.js`). Verified directly: every agent they fan out to (the
  six auditors in `AUDITORS`, plus `premortem-auditor`) is granted only `Read, Grep,
  Glob, Bash` in its frontmatter — no `Write`. There is no doc-write exposure on
  these paths, so they're excluded on evidence, not merely unmentioned.
- **`commands/work-through.md`'s plan-time instruction** to write the epic pre-mortem
  register (`docs/studious/premortems/<slug>-epic.md`) at plan approval, before any
  story runs. Not named in the acceptance criteria, and it's a different actor (the
  orchestrating assistant reading `work-through.md` directly at plan time) than a
  dispatched gate agent recording a verdict in the same breath.
- **Verdict vocabulary, retry caps, merge logic, or any other part of
  `epic-driver.js`** untouched by this ordering concern — explicit in the acceptance
  criteria.
- **Deduplicating the now near-identical "Record the verdict" boilerplate** across
  the two command files, or folding this rule into `reference/prompt-contract.md`'s
  shared blocks. That consolidation is `prompt-contract-dedup` (#92), a separate
  story in this epic; this story states the rule in place three times, it doesn't
  extract shared infrastructure (see Alternatives considered).

## Alternatives considered

- **Enforce the ordering in `bin/gate-ledger` itself** — e.g., `cmd_record` refuses
  to record, or auto-commits, when the working tree is dirty. Rejected: deciding
  *which* uncommitted files are "this gate's doc" versus an unrelated in-progress
  change is judgment, not bookkeeping, and belongs to the prompt per "code owns
  bookkeeping; prompts own judgment." A blanket dirty-tree check would false-positive
  on any unrelated uncommitted file in the tree; a smarter check would need its own
  fragile detection of what the gate itself wrote. #99 is explicit that this is
  "fail-safe today... noise reduction, not a correctness fix" — that framing doesn't
  justify new tool-level logic. Worth revisiting only if the prompt-level rule proves
  unreliable in practice.
- **Fold the rule into `reference/prompt-contract.md`'s shared blocks**, stamped in
  the same way the injection-defense preamble is injected into dispatched
  subagents. Rejected for this story: `prompt-contract.md`'s blocks are injected into
  *dispatched subagents* (product-reviewer, premortem-auditor, the six auditors) at
  the point they begin reviewing; this rule instead belongs at the very end of the
  *orchestrating* command's own flow, immediately before a `gate-ledger record` call
  the orchestrator itself runs — a different point in the prompt, a different
  audience. Bundling it into the shared contract would just relocate the
  duplication, and general prompt-contract dedup is explicitly `prompt-contract-dedup`
  (#92)'s job, not this story's.
- **Fix only the observed incident** (the finale acceptance dispatch) and leave
  `gate-design-review.md`'s prescribed pre-mortem write unaddressed. Rejected: the
  same `cmd_status` sha-vs-HEAD mechanism applies identically to the prescribed
  write; the acceptance criteria explicitly names both command files, and leaving one
  unfixed would leave a known, structurally-identical gap in the file `/gate-design-review` documents.

## Open questions

- **Exact wording and placement within each file** — whether the rule reads as a
  leading sentence in the existing "Record the verdict" section, a new one-line
  subsection, or folded into the existing closing paragraph — is a build-phase
  detail. Left to build, informed by keeping each file's diff minimal against its
  current structure (both command files already share near-identical "Record the
  verdict" boilerplate — see Alternatives considered on why this story doesn't
  consolidate it).
- **Whether the per-story `gatePrompt()` gap** (Out of scope, above) needs its own
  follow-up issue now, or should surface later as a finding once this fix's pattern
  is in place. I'd lean toward filing it so it doesn't get lost, but that's the
  maintainer's call, not this design's to make.
