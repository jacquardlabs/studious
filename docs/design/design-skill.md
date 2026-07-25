# Design: `/design` (batch interview, forks, sectioned doc, viva loop)

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: `skills/design/SKILL.md` is still the M1 stub
("Do not invoke for actual design work yet; there is no behavior behind
this file"). Every design doc this project has produced so far — six of
them, all real, all gate-reviewed, all merged (`build-scripts`,
`discipline-skill`, `build-skill`, `rough-in-inspector`, `finish-skill`,
`plan-lint`) — was hand-authored by a human/agent standing in for `/design`,
one session at a time, because there is nothing else to invoke. That is
precisely the "ad hoc prompting" `PRODUCT.md` says jig exists to replace,
paid by this project against itself, on every story so far. This story
removes that tax for every future story, starting with M2's own sibling
(`design-lint`, issue #9, still un-designed as of this writing — a natural
first real target once this skill ships; see Operational readiness).

This is also the concrete unlock for the epic goal: "so a real feature idea
can be turned into a `/gate-design-review`-ready design doc without
hand-authoring." Without this story, `PRODUCT.md`'s critical user journey 1
(Full cycle) has no first step — `/gate-should-we-build` → `/design` is the
journey's opening edge, and today it dead-ends immediately after the first
gate.

**The blocking dependency named in `PRODUCT.md`'s "Current known problems"
and issue #8's own comment is now clear.** M2 was explicitly gated on
[viva#101](https://github.com/jacquardlabs/viva/issues/101) (viva-qa didn't
register as an invokable Skill) closing — confirmed **closed**, along with
the other two prerequisites the M0 paper dogfood surfaced,
[viva#112](https://github.com/jacquardlabs/viva/issues/112) (qa-mode
process leak) and [viva#113](https://github.com/jacquardlabs/viva/issues/113)
(resume-on-signed-off-doc documentation gap) — both closed, and the fix
for #113 is exactly the resume behavior this design's viva-loop step relies
on (see Proposed design, Step 6). [viva#115](https://github.com/jacquardlabs/viva/issues/115)
(coarser-heading absorption) is also closed but is a `/plan`-doc-shaped
concern (jig issue #23), not this skill's — noted in Out of scope. The real
invocation contracts for `/viva-qa` and `/viva` (read directly from the
installed plugin, not re-derived from the pre-M0 friction report) are the
grounding for every mechanical detail below.

## Proposed design

One file changes behavior: `skills/design/SKILL.md` replaces its M1 stub
with the real procedure below, per issue #8's six-step summary and this
story's acceptance criteria. No script changes — `scripts/design-lint`
is called, not modified (it's the sibling story's own artifact; see Out of
scope and Operational readiness for how this design treats it as a
contract, not an implementation it owns).

### Step 0 — Inventory (before any question)

Read `PRODUCT.md`, `DESIGN.md`, and `CLAUDE.md` at the target project's
root, plus whatever code the feature ask actually touches (`Grep`/`Glob`
scoped to the named area, not a full-repo read) — in that order, always,
with no flag to skip it. This is the acceptance criteria's first line
verbatim and the same discipline `task-execution-discipline` already
requires of a fresh `/build` executor (read first, guess never). If a
prior `/gate-should-we-build` verdict exists (studious installed,
`gate-ledger` on `PATH`), read it too — it's framing context for the
interview, not a hard input this design requires standalone-capable
operation to depend on.

### Step 1 — Resolve the feature ask

One input: a one-line description of the feature idea (an argument, or the
conversation's own prior context if the human already stated it). No
schema beyond that — `/design`'s only structured input from here on is
what it writes itself (`.viva/qa-input.json`).

### Step 2 — Batch interview (viva-qa)

Real invocation contract, from the installed `viva-qa` skill's own
`SKILL.md` (not re-derived, not guessed): write `.viva/qa-input.json` —

```json
{
  "mode": "qa",
  "context": "<one-sentence feature description>",
  "questions": [
    {"id": "q1", "text": "...", "hint": "[intent] ...", "choices": [...], "recommended_choice": "..."}
  ]
}
```

— invoke `/viva-qa`, read `.viva/answers.json`. **5–9 questions in round
1**, each tagged with why it's asked. Reuse the exact four-tag taxonomy the
M0 paper dogfood already validated in a real session rather than inventing
a new one: `[intent]` / `[contract]` / `[experience]` / `[friction]`. Since
`qa-input.json`'s schema has no dedicated tag field, the tag is prefixed
onto the question's own `hint` (a real, named schema gap — see Open
questions — not silently worked around by inventing an unparsed field).

**Round 2 is conditional, never automatic**: only if round 1's answers open
a genuinely new fork — a question whose answer branches design direction
in more than one viable way, and that round 1 didn't already ask about.
Round 2, if it happens, asks only the newly-opened questions, not a
re-ask of round 1. **A third round would be needed** (round 2's answers
still leave an unresolved fork that needs more information than the human
can supply in-session) → stop. Do not run round 3, do not draft
`design-<slug>.md`. Report **NEEDS RESEARCH**, naming the specific
unresolved fork(s), and end the session there — the human does the
research (a spike, prior art, a stakeholder conversation) outside `/design`
and re-invokes fresh once it's resolved. Nothing is written to
`docs/design/` on this path — a half-drafted, un-lintable doc left on disk
would be worse than none.

### Step 3 — Forks (2–3 options, one recommendation)

A fork opened by the interview (or discovered while drafting) is presented
with **2–3 options, tradeoffs for each, and exactly one recommendation**.
This can — and per the M0 dogfood's own finding, should — ride the *same*
batch-interview round as ordinary questions: "batch interview and fork
presentation are conceptually two steps in jig's spec but mechanically the
same thing in viva's qa schema" (finding 5). No second server round is
needed just to separate them.

**The recommendation uses `recommended_choice`, not prose convention left
to the calling agent's discretion.** `viva-qa`'s schema (as shipped today,
not as it was at M0 dogfood time) carries an optional `recommended_choice`
field per question — it must exactly match one entry in that question's
own `choices`, renders as a "recommended" badge, and is advisory only
(never pre-selected). This closes the exact gap the M0 friction report
named by number (finding 5: "viva's `choices` schema has no field for
'this option is recommended'... If jig's `/design` implementation wants
recommendations to actually reach the human, that needs to become an
explicit convention") — the schema itself has since grown that field, so
this design commits to using it, mechanically, every time a fork is
presented; never a "(recommended)" string improvised into `text` or
`hint`. The *reason* for the recommendation still belongs in `hint` or the
choice text itself — `recommended_choice` names which option, not why.

### Step 4 — Draft `design-<slug>.md`

Written to `docs/design/<slug>.md` — the exact path and one-file-per-story
naming all six of this project's own prior design docs already established
(`docs/design/finish-skill.md`, `docs/design/build-skill.md`, etc.), not a
new location. **5–8 sections, each with a named consumer** (the acceptance
criteria's own words), satisfying both `DESIGN.md`'s Formatting section and
studious's `reference/design-doc-contract.md` at once. How those two
sources reconcile is itself a fork this design rules on — see the fork
below, since it is not a trivial "just do both" and the ruling changes
which headings the drafted doc actually carries.

**Fork: which section-heading convention does `design-<slug>.md` use?**

`DESIGN.md`'s Formatting section names one convention verbatim, sourced
from the ratified handoff (§5.1 step 4) and empirically produced once, by
hand, in the M0 paper dogfood (`design-viva-unified-session.md`, 7
sections, signed off): **Intent, Experience, Contracts, Approach,
Assumptions, Not doing, Risks.** `reference/design-doc-contract.md` names a
*different* 7 required sections — **Problem & persona, Proposed design,
User journey, Out of scope, Alternatives considered, Operational
readiness, Open questions** — and explicitly says heading text is
flexible: "Sections may carry any heading text as long as the content
answers the mapped question." These are not the same 7 names, and nothing
before this design doc has ruled which one `/design`'s own output actually
uses.

The tie-break is direct evidence, not preference: **every one of this
project's six already-shipped, already-gate-design-reviewed design docs
uses the contract's headings, not the handoff's.** Not one of them is
titled "Intent" or "Contracts." `DESIGN.md`'s own header already flags why:
its Formatting section is "still extracted from the project's ratified
handoff document, not from running code," and asks to be re-run "once
M2–M6 land real implementations." The M0 dogfood predates any of jig's own
code and was never itself checked against `design-doc-contract.md` (that
document didn't yet govern jig's practice) — six real, gate-passed
counterexamples authored since then are stronger grounding than one
paper exercise that predates the gate.

| Option | Shape | Tradeoff |
|---|---|---|
| A — Handoff-literal headings (Intent/Experience/Contracts/Approach/Assumptions/Not doing/Risks) | Matches `DESIGN.md`'s text and the M0 precedent exactly | Diverges from all six real shipped docs; `Operational readiness` (a *required* contract section — rollout/rollback/monitoring) has no clean home under any of these seven names, so satisfying the contract would mean inventing an eighth section or burying ops content inside "Risks" where the contract's reviewer wouldn't expect to find it |
| B — Contract-canonical headings (Problem & persona/Proposed design/User journey/Out of scope/Alternatives considered/Operational readiness/Open questions), each carrying an explicit **Consumer:** line | Matches all six real shipped docs; every contract-required section has an obvious, correctly-named home; `DESIGN.md`'s own "named downstream consumer" ask is met by the added Consumer line, not by the heading text itself | `DESIGN.md`'s Formatting section, read narrowly, still names the other seven words — this design doc is itself evidence that bullet is stale (see Open questions) |
| C — Hybrid: contract headings with the handoff's names parenthetically (e.g. "## Proposed design (Approach)") | Nominally honors both texts | Adds a naming veneer with no reader benefit over B; the two vocabularies don't even map one-to-one (see table below), so a parenthetical alias per heading would be actively misleading in the cells that don't correspond 1:1 |

**(recommended): B.** Matches uninterrupted established practice
(CLAUDE.md's own "minimize structural drift, prefer reuse over creation"),
gives every contract-required section — Operational readiness in
particular — an unambiguous home, and satisfies `DESIGN.md`'s actual
requirement (a named consumer per section) without adopting headings this
project has never once used for real. Approximate correspondence, for
traceability (not a literal per-cell mapping — several handoff names
distribute across more than one contract section, and vice versa):

| Contract heading (used) | Consumer | Nearest handoff-era name(s) |
|---|---|---|
| Problem & persona | product-reviewer Q1; the human deciding to fund the work | Intent |
| Proposed design | product-reviewer Q2/Q6; `/plan`'s spine-building step | Experience, Contracts, Approach |
| User journey | product-reviewer Q3; `/plan`'s task-boundary decisions | Approach |
| Out of scope | product-reviewer Q4 | Not doing |
| Alternatives considered | product-reviewer Q5; future readers reconsidering a rejected path | (folded into "Not doing" in the M0 precedent — see Alternatives considered below) |
| Operational readiness | `/gate-audit`'s operability lane; `/build`'s rollout-tier verification | *(no clean equivalent — the actual gap this fork resolves)* |
| Open questions | the human sponsor; the next `/design` revision round | Assumptions, Risks |

### Step 5 — Call `design-lint`, fix before viva

`scripts/design-lint <path>` runs on the freshly-drafted doc before any
viva round launches. This design does not invent `design-lint`'s internal
checks (that is issue #9's own story) — it derives the *contract*
`design-lint` must honor from the same two sources Step 4 just reconciled:
`DESIGN.md`'s Formatting rule (5–8 sections, named consumer) and
`design-doc-contract.md`'s seven required sections, plus issue #9's own
stated checks (concrete contract shapes, checkable assumptions, failure
paths covered, every fork carrying a recorded ruling). The **exit-code
contract** this design assumes is the one every sibling lint/verify script
in this repo already uses — `verify` and the just-designed `plan-lint`
both commit to 0 (clean) / 1 (violations, all printed) / 2 (usage error,
e.g. missing file or zero recognized sections) — not a new convention
invented here. A non-zero exit is fixed and re-linted before Step 6 ever
launches a server; `/design` never starts a viva round against a
lint-failing doc, per the acceptance criteria's own wording.

### Step 6 — viva loop (one card per section)

Launch per `viva`'s own documented Steps 1–5: `parse_sections.py` splits on
`##` (this doc's own 7 sections → 7 cards), the server opens a browser tab,
and the loop is launch → wait for verdicts → act → rewrite & re-arm | finish
until every section is `approved`. Nothing about that loop is
reimplemented here — it's read, not modified.

**Correctly distinguishing a fresh round from a resume matters and is
explicit, not left to "clear stale state" by rote.** Three distinct
situations, matching `viva`'s own now-documented (issue #113) branches:

1. **A brand-new session, doc never reviewed before** → the default block:
   clear `.viva/` state, parse round 1, launch. No `--prior-input`/
   `--prior-verdicts`.
2. **Round 2+ of a still-live session** (a `changes`/`info` verdict came
   back) → never touches the clear-state block at all; the running
   server's own round files are still on disk. This is `viva`'s ordinary
   step 4.
3. **A fresh session resuming review on an already-signed-off doc** — the
   case a **`REVISED`** re-invocation of `/design` hits every time (gate
   feedback, or a hand-edit since a prior sign-off): detect it by the
   doc already carrying a `## Revision History` heading, copy the prior
   session's highest-numbered `review-input-rN.json`/`review-rN.json`
   pair to `prior-review-input.json`/`prior-review-verdicts.json` (names
   the clear-state glob cannot match), run the clear-state block safely
   now that the copies are protected, then parse round 1 **with**
   `--prior-input`/`--prior-verdicts` pointed at those copies before
   launching. This is exactly `viva`'s own documented resume procedure,
   used, not reinvented — the M0 friction report's finding 3 ("I
   personally destroyed round-1 carry-forward state by following
   SKILL.md's own documented steps literally") is precisely the trap a
   fresh-context fallback to the generic clear-state block would walk
   `/design` into on every `REVISED` re-run; this design commits to
   recognizing case 3 explicitly rather than letting it collapse into
   case 1.

### Step 7 — Hand off

`command -v gate-ledger` (the same detection idiom `/finish`'s cctx check
already establishes for a sibling plugin, `command -v cctx`) decides the
branch: **found** → tell the developer to run `/gate-design-review` next.
**Not found** → report the verdict and stop there explicitly — "studious
not installed; skipping the `/gate-design-review` hand-off" — never a
silent gap (principle 10).

### Verdicts

| Verdict | When |
|---|---|
| `DESIGNED` | Every section of `design-<slug>.md` reaches `approved` in the viva loop; `design-lint` was already clean. |
| `NEEDS RESEARCH` | The interview's round 2 still leaves an unresolved fork that would need a round 3. No doc is drafted or committed. |
| `REVISED` | A previously-`DESIGNED` (or previously-`REVISED`) doc is re-drafted — after a studious `/gate-design-review` REVISE/RETHINK, or a direct human request — and re-signed-off via the resume path (Step 6, case 3). |

### Principle alignment

"Recommend one action; the human decides" is Step 3's whole shape:
`recommended_choice` names one option, never pre-selects it. "Nothing signs
off on itself" is why Step 5 runs a real, separate script rather than
`/design` asserting its own doc is well-formed, and why sign-off itself is
a human viva round, never a self-report. "Standalone-capable" is Step 7's
explicit, named studious-absent path. "Anti-cleverness tripwire" is why
this design adds no named sub-roles or ceremony beyond the plain
interview → forks → draft → lint → viva sequence issue #8 already states.

## User journey

Walks `PRODUCT.md` critical user journey 1 (Full cycle), the step this
story adds — the developer has just gotten a `PROCEED`-shaped verdict (or
has skipped straight here, studious not installed) on a feature idea:

1. The developer invokes `/design "<feature idea>"`. `/design` reads
   `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`, and the touched code area before
   asking anything — the developer never has to re-explain context the
   inventory could have found itself.
2. `/design` writes 7 tagged questions to `.viva/qa-input.json`
   (`[intent]`/`[contract]`/`[experience]`/`[friction]`), two of them
   forks with a `recommended_choice`, and invokes `/viva-qa`. A browser tab
   opens; the developer answers all 7 in one sitting.
3. One answer opens a genuinely new fork not covered in round 1 — `/design`
   asks 2 more questions in a round 2, same tab. The developer answers;
   nothing is left unresolved.
4. `/design` drafts `docs/design/<slug>.md`, 7 sections
   (Problem & persona → Open questions), each with a Consumer line, both
   forks recorded with their tradeoffs and the recommended option marked.
5. `/design` runs `scripts/design-lint docs/design/<slug>.md`. It reports
   one violation (a `Read first`-shaped claim with no checkable referent).
   `/design` fixes it and re-lints clean before touching viva.
6. `/design` launches a viva review round on the doc — 7 cards, one per
   section. The developer approves 5 outright and requests changes on 2;
   `/design` rewrites and re-arms; round 2 shows only the 2 changed cards,
   the other 5 collapsed. Everything approves.
7. `command -v gate-ledger` succeeds — `/design` reports **DESIGNED** and
   tells the developer to run `/gate-design-review` next.
8. Studious's gate comes back **REVISE** two days later (a separate
   session). The developer re-invokes `/design` in revision mode. `/design`
   recognizes the doc already carries a `## Revision History` heading,
   preserves the prior round files, clears state safely, and launches
   round 1 with `--prior-input`/`--prior-verdicts` — 5 sections show
   pre-approved and collapsed, only the 2 the gate flagged reopen. The
   developer approves both. `/design` reports **REVISED**.

No step of this journey changes shape from what `PRODUCT.md` and issue #8
already committed to; this story is what actually walks it, replacing six
stories' worth of by-hand proxying.

## Out of scope

- **The mockup sub-step (issue #10).** Per handoff §8, this was explicitly
  additive-not-structural and deferred "post-dogfood." The dogfood and its
  friction report have since landed (`docs/jig/dogfood/FRICTION-REPORT.md`),
  so the deferral's own stated condition is met — this design makes an
  actual ruling rather than repeating the bounce.

  **Fork: build a mockup sub-step now, or defer again?**

  | Option | Shape | Tradeoff |
  |---|---|---|
  | A — Build a minimal mockup step now (e.g., an optional wireframe/image-attachment capture folded into the batch interview, using `viva-qa`'s existing `attachments` support on an answer) | Unblocks issue #10 immediately | Zero real evidence it's needed: none of this project's own six shipped design docs, nor its M0 dogfood target (viva#109, a backend/session-lifecycle feature), had a UI surface to mock up. This story's own acceptance criteria never mentions a mockup step. Building it now is speculative generality against a use case that hasn't shown up once. |
  | B — Defer again, with a concrete, falsifiable trigger instead of "post-dogfood" repeated verbatim | Costs nothing today; the handoff itself calls this additive, so it can be bolted on later without touching Step 2–6's core loop | Issue #10 stays open a while longer |
  | C — Close issue #10 outright as permanently out of scope | Removes the recurring re-litigation entirely | Forecloses a real future need: jig's secondary persona (a standalone user with no other jacquardlabs tooling) could invoke `/design` against *their own* project's UI-heavy feature, where jig itself having no visual UI (`DESIGN.md`'s own framing) is irrelevant to what `/design`'s *output* might need to show |

  **(recommended): B.** Deferred, with a stated, concrete trigger this time
  rather than a repeat of "post-dogfood": revisit issue #10 the first time
  a real `/design` invocation is actually run against a feature with a
  genuine UI surface (a web/TUI/dashboard feature in some consuming
  project) and the lack of a mockup step is felt in that session, not
  before. Building it speculatively against zero real sessions would
  violate "prefer the simplest approach first" for a capability nothing
  has needed yet; permanently closing it would foreclose a legitimate need
  the secondary persona could plausibly hit. This is the recorded ruling
  the epic pre-mortem (risk #4) asked this doc to make explicitly rather
  than silently re-bounce.

- **`scripts/design-lint`'s own implementation.** Issue #9's story, not
  this one. This design derives the *contract* `/design` calls (Step 5)
  from `DESIGN.md` + `design-doc-contract.md` + issue #9's stated checks —
  it does not specify `design-lint`'s internals.
- **Any change to `/plan`, `PLAN.md`, or issue #23** (the Not-here
  follow-ups heading-level fix) — M3's job, unrelated to `/design`'s own
  output shape.
- **New viva features.** If this design surfaces a genuine viva gap (the
  `qa-input.json` tag field, named in Open questions), it's filed upstream
  as a viva issue, never patched from jig's side.
- **CI wiring for `design-lint`.** `CLAUDE.md` already notes Ruff isn't
  wired into a CI job yet for this repo; the same applies here — tracked
  separately, not this story's job.
- **Resolving which target repo `/design` runs against.** Like every other
  jig skill, `/design` assumes it's invoked inside the target project's own
  worktree — no repo-selection flag or multi-repo mode.

## Alternatives considered

1. **A separate, second viva session for the review round**, launched only
   after the QA server is fully torn down. Rejected: the real, installed
   `viva-qa` skill documents a same-tab hand-off (`POST /next-round`
   against the still-live QA server's URL) built for exactly this case —
   using it costs nothing extra and avoids a second manual browser
   reconnect the M0-era design (`design-viva-unified-session.md`) had to
   invent a whole new `/handoff` endpoint to avoid.
2. **Leaving the fork recommendation to the calling agent's own
   discretion** (a "(recommended)" string improvised into `text` or
   `hint`, as the M0 dogfood actually did, per friction finding 5).
   Rejected: already empirically failed once — the dogfood's own
   recommendation never reached the human in a structured way. The schema
   has since grown a real field (`recommended_choice`) for exactly this;
   using it is strictly better than reinventing a text convention the
   schema no longer requires.
3. **The handoff-literal section headings** (Intent/Experience/Contracts/
   Approach/Assumptions/Not doing/Risks) for `design-<slug>.md`. Rejected:
   diverges from all six of this project's own shipped, gate-passed design
   docs, and leaves `Operational readiness` — a section the contract
   requires — with no natural home (see the fork in Proposed design).
4. **Blocking this story's own build phase on issue #9 (`design-lint`)
   landing first**, via a hard sequential dependency between the two epic
   stories. Rejected as a *blanket* rule: `/design`'s own `SKILL.md` logic
   (Steps 0–4, 6, 7) needs nothing `design-lint` provides and can be built
   against the derived exit-code contract (Step 5) independently — matching
   the epic pre-mortem's own resolution guidance (risk #1: confirm the
   design doc cites the shared schema, not an invented one). What *does*
   require `#9` to be real is this story's own required end-to-end
   demonstration, which can't exercise a real lint pass against a stub that
   exits 0 unconditionally — noted as a build-phase sequencing fact in
   Operational readiness, not a full story-level block.

## Operational readiness

`skills/design/SKILL.md` is a prompt file read by a Claude Code session; no
deployed service, no data migration.

- **Rollout**: replaces the M1 stub's frontmatter/body in place — the same
  pattern `build-skill` and `finish-skill` both already used for their own
  rollout. No feature flag, no staged rollout.
- **Rollback**: `git revert` the commit that replaces the stub. Nothing
  under `scripts/` or `skills/task-execution-discipline/` is touched by
  this story, so no other component is affected by a rollback.
- **Failure visibility**: a `design-lint` failure is reported by name
  (which check, which section) and blocks the viva round entirely — never
  a silent partial lint. A `viva`/`viva-qa` launch failure (the skills'
  own pre-existing guard: `.viva/server.url` already present, or
  `server.py` missing entirely) surfaces verbatim, exactly as `viva`'s own
  `SKILL.md` already specifies — `/design` invents no retry logic on top
  of it. `NEEDS RESEARCH` **is** this design's primary graceful-failure
  path — an unresolved fork stops the session cleanly rather than
  forcing a guessed answer through to a drafted doc.
- **A known, accepted limitation**, named rather than silently worked
  around: `viva-qa`'s `qa-input.json` schema has no dedicated field for
  "this question's asking-tag" or "this is a fork, not an ordinary
  question" — both ride inside `hint`/`text` today (Steps 2–3). This is a
  real schema gap on viva's side; it's noted here as an accepted,
  low-cost workaround (see Open questions for the upstream fix this isn't
  attempting to make).
- **Required demonstration** (this story's own acceptance criteria: a real
  target produces a signed-off `design-<slug>.md` via a real viva round).
  This project's own sibling story, `design-lint` (issue #9), is
  currently un-designed — a natural, real, immediately-available target
  for `/design`'s own required demonstration once this skill ships, and
  doing so would simultaneously produce `design-lint`'s design doc as a
  useful side effect rather than a throwaway exercise. This is a strong
  build-phase recommendation, not a hard requirement of this design —
  the exact target is a build-phase decision (see Open questions).

## Open questions

- **`qa-input.json`'s missing tag/fork-marker field.** Today's workaround
  (Step 2/3: piggyback the tag onto `hint`) is functional but informal —
  worth a real upstream viva feature request once this design ships and
  the workaround's cost is felt over more than one invocation. Not filed
  here; filing it is a build- or post-build-phase judgment call, not a
  design-time one.
- **Resolved during acceptance fix-and-retry, not deferred as originally
  planned.** This bullet originally read: `DESIGN.md`'s Formatting section
  is stale against this design's own ruling, flagged for a future
  `/deep-review interface` pass or a `/finish`-time decision patch, not
  fixed by this design doc directly. That deferral turned out to be unsafe
  — this story's own Step 5 hard-depends on `design-lint` (which cites
  `DESIGN.md` as its authority) accepting output drafted against the
  contract-canonical seven, so leaving `DESIGN.md` stale meant the happy
  path could never reach `DESIGNED` once `design-lint` shipped for real.
  `DESIGN.md`'s "Design doc structure" line has been updated in place (same
  fix cycle as this note) to name the contract-canonical seven, matching
  this doc's own ruling instead of the handoff's.
- **Also resolved during acceptance fix-and-retry, not still open as
  originally recorded.** This bullet originally read: `scripts/design-lint`
  (issue #9, sibling story, already merged) has not received the matching
  patch, verified directly against a real invocation that reported 11
  violations and exited `1`. That was already stale by the time it was
  written — the sibling `design-lint-reconcile` story
  (`docs/design/design-lint-reconcile.md`, merged) had already reconciled
  `design-lint`'s `CANONICAL_SECTIONS`/`REQUIRED_SECTIONS` constants to
  `design-doc-contract.md`'s seven, and remapped Checks 2–4's old
  `Contracts`/`Assumptions`/`Experience` lookups to `Proposed design`/
  `Problem & persona`/`User journey` respectively. A real invocation
  against this doc now confirms the clean state directly:
  `scripts/design-lint --doc docs/design/design-skill.md --repo .` reports
  a clean pass (5 checks, 0 violations), exit `0`.
- **The real target for this story's required end-to-end demonstration**
  (see Operational readiness) — `design-lint` (issue #9) is the strong
  build-phase recommendation, but the final choice is the build phase's,
  not fixed here.
- **Whether `/design` should read a prior `/gate-should-we-build` verdict**
  as interview-framing context when studious is installed (Step 0)
  — a nice-to-have refinement, not resolved here, and not a blocker for
  this story's own acceptance criteria.
