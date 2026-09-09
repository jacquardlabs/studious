# Design records stay disposable — 2026-09-05 re-affirmation, amended 2026-09-09

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

## Amendment 2026-09-09 — the register is disposable too (#397)

**Overturns one line of the ruling above:** the pre-mortem register is no longer durable.
It moves from `docs/studious/premortems/<slug>.md` (committed by `/review`) to
`docs/design/<slug>-premortem.md`, gitignored beside the design doc it was written
against, read from the working tree by the work episode's pre-mortem lane, removed by
`/ship` at closeout. The 56 committed registers were deleted in the same change; git
history is their archive (`git show <sha>:docs/studious/premortems/<slug>.md`).

Why: the register's only consumer runs pre-merge, the same lifecycle as the doc it
derives from. Its second job — the committed-spec substitute — was asserted above, never
exercised: no incident has asked a register "why does this code look like this", while
56 registers accumulated for designs whose docs are gone. Since 2026-09-09 the design
gate is off by default (#415), so a register exists only when `/shape` ran; a durable
class that most stories never produce is a drift surface, not a spine. The durable
record of a change is its PR: the evidence table `/ship` assembles and the PR's own prose.

### Every artifact class, one table

| Artifact | Path | Class | Written by | Removed by |
|---|---|---|---|---|
| Design doc | `docs/design/<slug>.md` | disposable | `/shape`, or any route | `/ship` at closeout |
| Pre-mortem register | `docs/design/<slug>-premortem.md` | disposable | `/review` design episode | `/ship` at closeout |
| Plan | `PLAN.md` | disposable | `/build` Step 0 | `/ship` at closeout |
| Build evidence | `.studious/build-evidence/`, `.studious/evidence/` | local state | `/build`, the evidence hook | `gate-ledger gc` |
| Gate ledger, work files | `.studious/gates/`, `.studious/work/` | local state | `bin/gate-ledger` | `gate-ledger gc` |
| PR body and evidence table | the PR | durable | `/ship` | never |
| Dated build report | `docs/studious/build-reports/<date>-<slug>-build-report.md` | durable | `/ship` | never |
| Review reports | `docs/studious/<area>-reviews/<date>-<area>-review.md` | durable | `/health` | never — trend history is their reason to exist |
| Retros | `docs/studious/retros/<date>-retro.md` | durable | `/retro` | never |
| Decision journal | `docs/studious/decisions.jsonl` | durable, never auto-committed | `/bet` | never |
| Decision records | `docs/<topic>.md` | durable | the human | never |

A durable file cites a disposable one by issue or by `git show <sha>:<path>`, never by
path; `scripts/check_references.py` fails the build on a `docs/design/<name>.md` citation
in a shipped prompt or reference file.

**What would overturn this:** a real incident where the PR body and git history could not
answer "why does this code look like this" and a committed register would have. Name it
when reopening.
