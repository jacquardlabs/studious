---
name: design
description: Runs jig's /design workflow -- inventories PRODUCT.md, DESIGN.md, CLAUDE.md, and the touched code, a batch interview (viva-qa) of 5-9 tagged questions with forks presented as 2-3 options carrying one recommended_choice, a drafted design-<slug>.md (Problem & persona through Open questions, each section carrying a named consumer), a design-lint pass fixed before viva ever starts, and a viva sign-off loop that distinguishes a fresh round from a REVISED resume via --prior-input/--prior-verdicts. Use when the user says /design, hands over a feature idea to turn into a design doc, or a /build ESCALATED verdict routes back here for revision. Emits exactly one verdict -- DESIGNED, NEEDS RESEARCH, or REVISED -- and hands off to /gate-design-review when studious is installed, degrading explicitly otherwise.
---

# /design

You are the session that turns a feature idea into a `design-<slug>.md` a
human has signed off on, section by section, via a real viva review --
`PRODUCT.md`'s critical user journey 1 (Full cycle) opening edge, and the
landing spot for a `/build` `ESCALATED` verdict's hand-back (critical user
journey 3, Revision loop).

Read first, guess never, exactly once: **Step 0 is not optional and has no
skip flag.** Everything else in this file assumes it already ran.

## Input

One argument: a one-line description of the feature idea (or the
conversation's own prior context, if the human already stated it). No
schema beyond that -- the only structured input `/design` produces from
here on is what it writes itself (`.viva/qa-input.json`, then
`design-<slug>.md`).

## Step 0 -- Inventory (before any question)

Read, in this order, always:

1. `PRODUCT.md` at the target project's root.
2. `DESIGN.md` at the target project's root.
3. `CLAUDE.md` at the target project's root.
4. Whatever code the feature ask actually touches -- `Grep`/`Glob` scoped to
   the named area, never a full-repo read.

If a prior `/gate-should-we-build` verdict exists (studious installed,
`gate-ledger` on `PATH`), read it too -- framing context for the interview,
not a hard input this design requires standalone-capable operation to
depend on.

## Step 1 -- Resolve the feature ask

Take the one-line feature description from the argument, or from the
conversation's own prior context if the human already stated it. Nothing
else to resolve here.

## Step 2 -- Batch interview (viva-qa)

Write `.viva/qa-input.json`:

```json
{
  "mode": "qa",
  "context": "<one-sentence feature description>",
  "questions": [
    {
      "id": "q1",
      "text": "...",
      "hint": "[intent] ...",
      "choices": ["...", "..."],
      "recommended_choice": "..."
    }
  ]
}
```

Then invoke `/viva-qa` and read `.viva/answers.json` once it writes.

**5-9 questions in round 1.** Tag every question with why it's asked, using
the four-tag taxonomy the M0 paper dogfood already validated:
`[intent]` / `[contract]` / `[experience]` / `[friction]`. `qa-input.json`'s
schema has no dedicated tag field, so the tag is prefixed onto the
question's own `hint` (e.g. `"[contract] ..."`) -- a real, named schema gap
(see Open questions below), not silently worked around by inventing an
unparsed field.

**Write each question for a browser card the human answers in seconds.**
`text` is one sentence ending in a question mark; `hint` is the tag plus
one line of context, never a paragraph; each entry in `choices` is a short
option label with its tradeoff in a clause, not an essay per option. A
question the human has to re-read before answering costs more than the
answer is worth -- the batch's whole point is nine answers in one sitting.

**Round 2 is conditional, never automatic.** Only run it if round 1's
answers open a genuinely new fork -- a question whose answer branches
design direction in more than one viable way, and that round 1 didn't
already ask about. Round 2, if it happens, asks only the newly-opened
questions, never a re-ask of round 1.

**A third round would be needed** if round 2's answers still leave an
unresolved fork that needs more information than the human can supply
in-session. When that happens: stop. Do not run round 3, do not draft
`design-<slug>.md`. Report **NEEDS RESEARCH**, naming the specific
unresolved fork(s), and end the session there. Nothing is written to
`docs/design/` on this path -- a half-drafted, un-lintable doc left on disk
would be worse than none.

## Step 3 -- Forks (2-3 options, one recommendation)

A fork opened by the interview (or discovered while drafting) is presented
with **2-3 options, tradeoffs for each, and exactly one recommendation**.
This rides the *same* batch-interview round as ordinary questions -- batch
interview and fork presentation are mechanically the same thing in
`viva-qa`'s schema. No second server round is needed just to separate them.

**The recommendation uses `recommended_choice`, not prose convention.**
`viva-qa`'s schema carries an optional `recommended_choice` field per
question -- it must exactly match one entry in that question's own
`choices`, renders as a "recommended" badge, and is advisory only (never
pre-selected). Never improvise a `"(recommended)"` string into `text` or
`hint` instead -- that already failed once (see Alternatives below in the
design doc this implements). The *reason* for the recommendation still
belongs in `hint` or the choice text -- `recommended_choice` names which
option, not why.

## Step 4 -- Draft design-<slug>.md

Written to `docs/design/<slug>.md` -- the same path and one-file-per-story
naming every prior design doc in this project already uses.

**Exactly 7 sections, each with a named consumer.** Use `design-doc-contract.md`'s
seven section names -- the contract-canonical convention, matching
`DESIGN.md`'s own "Design doc structure" line (reconciled to these same
seven names, no longer the stale handoff-literal set, nor its old "5-8"
range now that design-lint enforces exactly 7 with no optional tier) --
because every design doc this project has actually shipped and
gate-reviewed uses these seven, and only these seven give
`Operational readiness` an unambiguous home:

1. **Problem & persona** -- Consumer: the human deciding to fund the work;
   product-reviewer Q1.
2. **Proposed design** -- Consumer: product-reviewer Q2/Q6; `/plan`'s
   spine-building step.
3. **User journey** -- Consumer: product-reviewer Q3; `/plan`'s
   task-boundary decisions.
4. **Out of scope** -- Consumer: product-reviewer Q4.
5. **Alternatives considered** -- Consumer: product-reviewer Q5; future
   readers reconsidering a rejected path.
6. **Operational readiness** -- Consumer: `/gate-audit`'s operability lane;
   `/build`'s rollout-tier verification.
7. **Open questions** -- Consumer: the human sponsor; the next `/design`
   revision round.

Give each section heading its own `Consumer:` line naming who reads it --
this is what satisfies `DESIGN.md`'s "named downstream consumer" requirement
without adopting headings this project has never used for a real, shipped
doc. Every fork raised in Steps 2-3 is recorded in the doc with its 2-3
options, tradeoffs, and the recommended option marked
`**(recommended): <letter>.**` with the reasoning stated -- never left
implicit in the interview transcript alone.

**Write each section as one review card.** Step 6's viva loop splits the
doc on `##` and puts one section per card in front of the human, who
approves or rejects it as a unit -- so draft for that judgment, not for
completeness theater. The section's first sentence carries its central
claim or decision; enumerable content (options, journey steps, exclusions,
open questions) is bulleted, not woven into paragraphs; a section stays
judgeable on one screen without scrolling. Length follows content -- `Out
of scope` may be five bullets; `Proposed design` may run longer -- but
nothing pads a card the reviewer must scroll past to approve.

## Step 5 -- Call design-lint, fix before viva

Run `scripts/design-lint --doc docs/design/<slug>.md --repo <worktree>` on
the freshly-drafted doc before any viva round launches -- the real script's
own CLI shape (`--doc` is required; a bare positional argument is a usage
error), matching how every sibling script in this repo (`scripts/verify`,
`scripts/evidence-capture`, `scripts/evidence-freshness`,
`scripts/build-report`) already takes `--repo <worktree>` rather than
assuming the process's own cwd. This is the same exit-code contract every
sibling lint/verify script in this repo already uses: `0` (clean), `1`
(violations, all printed), `2` (usage error -- e.g. missing file, a bad
`--repo`, or a positional call instead of `--doc`). Never a new convention
invented here.

**A non-zero exit is fixed and re-linted before Step 6 ever launches a
server.** `/design` never starts a viva round against a lint-failing doc --
if `design-lint` reports a violation, revise the doc and re-run
`scripts/design-lint` until it exits `0`. Exit `2` means the doc itself (or
the invocation) is malformed -- fix that structurally, not by editing
around the checker.

## Step 6 -- viva loop (one card per section)

Launch per `viva`'s own documented Steps 1-5: its parser splits the doc on
`##` into one card per section, the server opens a browser tab, and the
loop is launch -> wait for verdicts -> act -> rewrite & re-arm | finish
until every section is `approved`. Nothing about that loop is reimplemented
here -- it's read, not modified.

**The QA server from Step 2 is still live.** Hand off in the same browser
tab via `viva-qa`'s documented same-tab hand-off (`POST /next-round`
against the still-live QA server's URL) rather than tearing it down and
reconnecting a second time.

**Correctly distinguish a fresh round from a resume -- never "clear stale
state" by rote.** Three distinct situations, matching `viva`'s own
documented branches:

1. **A brand-new session, doc never reviewed before** -> the default block:
   clear `.viva/` state, parse round 1, launch. No `--prior-input`/
   `--prior-verdicts`.
2. **Round 2+ of a still-live session** (a `changes`/`info` verdict came
   back) -> never touches the clear-state block at all -- the running
   server's own round files are still on disk. This is `viva`'s ordinary
   step 4.
3. **A fresh session resuming review on an already-signed-off doc** -- the
   case a **`REVISED`** re-invocation hits every time (gate feedback, or a
   hand-edit since a prior sign-off): detect it by the doc already carrying
   a `## Revision History` heading. Then, **before** the clear-state block:
   copy the prior session's highest-numbered
   `review-input-rN.json`/`review-rN.json` pair to
   `prior-review-input.json`/`prior-review-verdicts.json` (names the
   clear-state glob cannot match), run the clear-state block safely now
   that the copies are protected, then parse round 1 **with**
   `--prior-input .viva/prior-review-input.json --prior-verdicts
   .viva/prior-review-verdicts.json` before launching. Discard the two
   copies once that parse succeeds.

A fresh-context fallback to the generic clear-state block on case 3 would
destroy round-1 carry-forward state -- exactly the trap the M0 friction
report's finding 3 names ("I personally destroyed round-1 carry-forward
state by following SKILL.md's own documented steps literally"). Recognizing
case 3 explicitly, every time, is what this step commits to instead of
letting it silently collapse into case 1.

A `viva`/`viva-qa` launch failure (the skills' own pre-existing guard --
`.viva/server.url` already present, or `server.py` missing entirely)
surfaces verbatim, exactly as their own `SKILL.md`s already specify --
`/design` invents no retry logic on top of it.

## Step 7 -- Hand off

Check `command -v gate-ledger`:

- **Found** -- tell the developer to run `/gate-design-review` next.
- **Not found** -- report the verdict and stop there explicitly: "studious
  not installed; skipping the `/gate-design-review` hand-off." Never a
  silent gap.

## Verdicts

| Verdict | When |
|---|---|
| `DESIGNED` | Every section of `design-<slug>.md` reaches `approved` in the viva loop; `design-lint` was already clean. |
| `NEEDS RESEARCH` | The interview's round 2 still leaves an unresolved fork that would need a round 3. No doc is drafted or committed. |
| `REVISED` | A previously-`DESIGNED` (or previously-`REVISED`) doc is re-drafted -- after a studious `/gate-design-review` REVISE/RETHINK, or a direct human request -- and re-signed-off via the resume path (Step 6, case 3). |

Report exactly one of these three tokens, never more than one, at the end
of every `/design` session.

## Open questions this skill inherits (not fixed here)

- `qa-input.json` has no dedicated field for a question's asking-tag or for
  "this is a fork, not an ordinary question" -- both ride inside
  `hint`/`text` today (Steps 2-3), a functional but informal workaround.
  Worth a real upstream viva feature request once the workaround's cost is
  felt over more than one invocation -- not filed by this skill itself.

(Two previously-listed items -- `DESIGN.md`'s stale handoff-literal section
names, and `design-lint`'s matching stale constants -- are resolved; see
`docs/design/design-lint-reconcile.md` and git history.)

## Why this shape

"Recommend one action; the human decides" is Step 3's whole shape --
`recommended_choice` names one option, never pre-selects it. "Nothing signs
off on itself" is why Step 5 runs a real, separate script rather than
`/design` asserting its own doc is well-formed, and why sign-off itself is a
human viva round, never a self-report. "Standalone-capable" is Step 7's
explicit, named studious-absent path. "Anti-cleverness tripwire" is why
this skill adds no named sub-roles or ceremony beyond the plain interview ->
forks -> draft -> lint -> viva sequence.
