# Design records stay disposable — 2026-09-05 re-affirmation

**Status:** ratified · **Date:** 2026-09-05 · **Ruling on:** [#313](https://github.com/jacquardlabs/studious/issues/313) · **Milestone:** [#20 (M0)](https://github.com/jacquardlabs/studious/milestone/20)

CLAUDE.md's "Where a design record lives" (ratified 2026-07-25, #219/#216/#181) makes
`docs/design/<slug>.md` and `PLAN.md` gitignored and branch-local, removed at closeout;
only the pre-mortem register (`docs/studious/premortems/<slug>.md`), the review reports
under `docs/studious/<area>-reviews/`, and decision records at `docs/` root outlive the
branch. #313 asked whether the software-factory work (M0 and after) should reopen that
rule, because Anthropic's AI-native SDLC playbook (2026-08-21) commits `intent.md`,
`spec.md`, and `plan.md` to version control and cites them from PR review, and #31 (spec
traceability) is only possible on that model.

## Decision

**The rule stands, unchanged.** The durable spine for a feature's history is the
pre-mortem register, `docs/studious/decisions.jsonl` (the `/bet` verdict journal,
`reference/decision-journal-format.md`), and the PR evidence table `/ship` assembles at
closeout — not a committed spec or plan. `docs/design/<slug>.md` and `PLAN.md` keep dying
at merge. **#31 stays parked by design**, not by oversight: it asks for traceability that
only a committed spec can give, and a committed spec is exactly what this ruling rejects.

## Why, against the alternative actually on the table

The playbook's `intent.md`/`spec.md`/`plan.md` triad is real prior art, not a strawman —
it is what a comparable vendor playbook does, and it is why this got re-litigated instead
of assumed. Rejected anyway, because a committed design record is **the fourth document
class** the 2026-07-25 rule exists to prevent, and the cost of that fourth class is
already on this repo's own record: `docs/superpowers/{plans,specs}/` held 42 of this
repo's own design records under a third-party product's name, and 35 had gone stale
before it was deleted rather than renamed. Traceability bought at that price — a growing
pile of specs nobody is committed to keeping current — is not traceability, it's drift
with a paper trail.

What retrieves a feature's design history instead: the pre-mortem register records
`Branch:` and `SHA:`, which resolve through git history without a path that expires. A
disposable doc that lived on a merged branch is one `git show <sha>:<path>` away for as
long as the branch's commits survive, which is exactly as long as anything else this repo
keeps.

## What would overturn this

If a future story needs #31's traceability badly enough to pay the fourth-class cost —
concretely, if the pre-mortem register + evidence table prove insufficient to answer
"why does this code look like this" for a real incident — reopen #313 with that incident
named. Don't reopen it on the strength of a vendor blog post alone; that evidence was
already weighed here and found insufficient on its own.
