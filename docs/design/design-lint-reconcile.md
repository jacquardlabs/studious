# Design: reconcile design-lint's section-name schema to design-doc-contract.md's seven

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today: `scripts/design-lint` (landed for real at issue
#9, `cf6b2fb`) validates a `design-<slug>.md` doc's section headings against
a seven-name vocabulary — `Intent`, `Experience`, `Contracts`, `Approach`,
`Assumptions`, `Not doing`, `Risks` (`scripts/design-lint:58-60`) — sourced
from `DESIGN.md`'s "Design doc structure" line. That line is itself labeled,
in `DESIGN.md`'s own header, as "still extracted from the project's ratified
handoff document, not from running code" — a caveat still true today. Every
design doc this project has actually authored and taken through
`/gate-design-review` — `docs/design/design-lint.md` and
`docs/design/finish-skill.md`, the only two real fixtures that exist — uses a
completely different seven-name vocabulary: `Problem & persona`,
`Proposed design`, `User journey`, `Out of scope`, `Alternatives considered`,
`Operational readiness`, `Open questions` (verified: `grep -n "^## "
docs/design/design-lint.md docs/design/finish-skill.md` returns exactly these
seven headings, in this order, in both files) — the same seven names
studious's `reference/design-doc-contract.md` requires. This is not a close
call the linter mostly gets right: it is checking for a vocabulary no real
doc in this repository has ever used.

The sibling `design-skill` story's own design doc (`docs/design/design-skill.md`
on branch `epic/m2-design-skill--design-skill`, not this branch) already rules
on this by name, through a passed `/gate-design-review`: Step 4's fork ("which
section-heading convention does `design-<slug>.md` use?") is decided in favor
of "Contract-canonical headings," on the direct evidence that "every one of
this project's six already-shipped, already-gate-design-reviewed design docs
uses the contract's headings, not the handoff's. Not one of them is titled
'Intent' or 'Contracts.'" That ruling means every future `design-<slug>.md`
`/design` drafts will carry the contract's seven names — `design-lint` checking
for the other seven is not a latent risk, it is a guaranteed first-run
failure the moment that story merges and a real developer invokes `/design`.

This is evidence, not conjecture. Running today's `design-lint` against the
one real doc that specifies its own checks fails outright:

```
$ uv run --no-project python3 scripts/design-lint --doc docs/design/design-lint.md --repo .
[FAIL] section count and vocabulary: section 'Problem & persona' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'Proposed design' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'User journey' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'Out of scope' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'Alternatives considered' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'Operational readiness' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: section 'Open questions' does not match jig's canonical section vocabulary — see DESIGN.md's Design doc structure
[FAIL] section count and vocabulary: missing required section 'Contracts' (Checks 2-4 presuppose it exists)
[FAIL] section count and vocabulary: missing required section 'Assumptions' (Checks 2-4 presuppose it exists)
[FAIL] section count and vocabulary: missing required section 'Experience' (Checks 2-4 presuppose it exists)
[FAIL] section count and vocabulary: only 0 of ['Intent', 'Approach', 'Not doing', 'Risks'] present; at least 2 are required to reach the 5-section floor (missing: Intent, Approach, Not doing, Risks)
[FAIL] fork rulings: fork q1 has no recorded ruling (no ruling-shaped clause found in the same sentence or bullet as any of its '(qN)' citations)
[FAIL] fork rulings: fork q4 has no recorded ruling (no ruling-shaped clause found in the same sentence or bullet as any of its '(qN)' citations)
[FAIL] fork rulings: fork q7 has no recorded ruling (no ruling-shaped clause found in the same sentence or bullet as any of its '(qN)' citations)
design-lint: docs/design/design-lint.md — 14 violation(s) across 2 check(s)
```

(The fork-ruling failures are a side effect of the same doc's own worked
example using the `(qN)` shorthand to *describe* the convention, not to cite a
real fork of its own — a false positive from Check 5 unrelated to this
story's scope, noted here for completeness and picked up again in Open
questions.)

Fourteen violations against a doc that passed a human product-reviewer gate
is the exact failure mode `design-lint`'s own design doc named as its
founding reason to exist: "a stub that always passes is structurally
indistinguishable from 'no check ran at all.'" A linter that *fails* every
real doc this project has ever produced is the mirror image of that same
failure — indistinguishable from "no usable check exists," except worse,
because `/design`'s own committed Step 5 ("a non-zero exit is fixed and
re-linted before Step 6 ever launches a server") means a developer hits this
wall on literally every invocation, with no edit to the draft that escapes
it, since the tool is checking for headings no correctly-authored doc will
ever carry.

## Proposed design

`scripts/design-lint`'s constants and two check-target lookups are updated in
place — same file, same CLI shape, same 0 (clean) / 1 (violations) / 2 (usage
error) exit contract this story's acceptance criteria does not touch. The
canonical section-name list becomes exactly `reference/design-doc-contract.md`'s
seven required sections:

```python
CANONICAL_SECTIONS = (
    "Problem & persona",
    "Proposed design",
    "User journey",
    "Out of scope",
    "Alternatives considered",
    "Operational readiness",
    "Open questions",
)
```

**Check 1's required/optional split disappears, not just its names.** The old
schema (`scripts/design-lint:58-63`) split seven names into three
unconditionally-`REQUIRED_SECTIONS` (because Checks 2-4 presuppose them) and
four `OPTIONAL_SECTIONS`, with a `MIN_OPTIONAL_FOR_FLOOR = 2` rule so a count
in `[MIN_SECTIONS, MAX_SECTIONS] = [5, 8]` could be reached without all seven
present. `reference/design-doc-contract.md` draws no such distinction: its
table is headed "## Required sections," seven rows, none marked optional, no
stated count range. There is no cell in the new source to remap the old
floor logic onto — it retires because the schema it approximated no longer
has an optional tier, not because this story invents a reason to drop it.
Check 1 becomes: exactly these seven headings present, once each, in any
order, no unrecognized top-level heading — a straight `== 7` requirement, not
a `[5, 8]` range. This matches the only two real fixtures without exception:
`docs/design/design-lint.md` and `docs/design/finish-skill.md` both carry
exactly these seven, no more, no fewer, no extras.

**Checks 2-4 are remapped onto whichever of the seven now carries that
semantic — not renamed onto whatever name looked closest.** Each row below
names the check, the section it targeted before, the section it targets now,
and the concrete evidence the mapping is grounded in (not just plausible):

| Check | Old section | New section | Rationale |
|---|---|---|---|
| 1 — section vocabulary & required set | 3 required (`Contracts`/`Assumptions`/`Experience`) + 4 optional-with-floor | all seven required, no optional tier | `reference/design-doc-contract.md`'s own table is titled "Required sections" with seven rows and no optional row — the source of truth this story reconciles against draws no required/optional line, so neither does the reconciled check. |
| 2 — concreteness (fenced block / table / ≥N artifact-shaped inline-code spans) | `Contracts` | `Proposed design` | `docs/design/design-skill.md`'s own Step 4 fork ruling (already through `/gate-design-review`) names `Proposed design` as the section `Experience, Contracts, Approach` all fold into under the contract's seven names — the *only* place in this repository anyone has actually reasoned through this exact correspondence. Confirmed directly, not just by that table: `docs/design/design-lint.md`'s own `Proposed design` section (its longest) is the one dense with backtick-quoted artifact names — `` `scripts/design-lint` ``, `` `plan-lint` ``, `` `verify` ``, `` `evidence-capture` `` — exactly the shape Check 2 already looks for, just under a renamed heading, not a redesigned one. |
| 3 — checkability (an interview-ruled or tree-resolvable claim, not a bare assertion) | `Assumptions` | `Problem & persona` | `reference/design-doc-contract.md`'s own "what good looks like" text for `Problem & persona`: "Names a persona and job-to-be-done from `PRODUCT.md` verbatim, not a paraphrase invented for this doc." That sentence *is* Check 3's founding principle — don't trust prose, check it against a real source — restated by the contract itself, just narrowed from "any repo path" to "grounded in `PRODUCT.md` specifically." Confirmed by both real fixtures without exception: `docs/design/design-lint.md`'s and `docs/design/finish-skill.md`'s `Problem & persona` sections both open with a blockquote that is a verbatim, word-for-word substring of `PRODUCT.md`'s own persona paragraph (`PRODUCT.md:28-30`) — not a paraphrase, an exact quote, in both of the only two real precedents available. |
| 4 — failure path (at least one failure-shaped clause alongside the happy path) | `Experience` | `User journey` | A direct rename of an unchanged semantic — `reference/design-doc-contract.md`'s own words, "Walks the primary persona through the feature end to end... Calls out any step that changes an existing journey," describe exactly what Check 4 already enforces. Confirmed directly: `docs/design/design-lint.md`'s own `User journey` section's step 3 already narrates a failure step in this shape ("`design-lint` exits non-zero, naming both..."). |

**Check 3's mechanism generalizes to three grounding buckets, not two.** The
old check accepted a bullet as checkable if it was either (a) tagged with a
`(qN)` interview-ruling citation, or (b) an inline-code span shaped like a
file path that resolves against `--repo`. Retargeted at `Problem & persona`,
the section's core claim — the persona and its problem — is checkable a third
way the old `Assumptions` section never needed, because it never made this
particular kind of claim: (c) a blockquoted excerpt that is a verbatim
substring of the project's own `PRODUCT.md`. All three buckets stay, because
`Problem & persona` sections in this repo's real docs use all three shapes:
the persona blockquote itself (bucket c), citations to non-`PRODUCT.md`
grounding like a premortem doc or a prior report (bucket b — e.g.
`docs/design/design-lint.md`'s own citation of
`` `docs/studious/premortems/m2-design-skill-epic.md` ``), and forward
references to a fork the interview already ruled on (bucket a, unused in the
two real fixtures today but not foreclosed). A `Problem & persona` section
with none of the three — a persona/problem claim asserted with no checkable
grounding at all — is the violation this check exists to catch, reported the
same way Check 3 always has: by naming the unchecked claim, not with a
generic "section failed."

**Checks 2 and 4's own internal mechanisms are otherwise unchanged** — same
fenced-block/table/artifact-span-count heuristic for concreteness (exact
floor a build-phase constant, per `reference/design-doc-contract.md`'s own
non-requirements clause, matching this project's established precedent of
leaving such constants to the build phase), same closed failure-token
vocabulary for the failure-path check. Only the section each looks up
changes.

**Check 5 (every `(qN)` fork carries a recorded ruling) is untouched.** It
already scans the whole document (`scripts/design-lint:347-370`) regardless
of section names, so no section-name remap applies to it — this story's
acceptance criteria names only Checks 1-4. Whether Check 5 still has a real
target to check against is a separate question, raised in Open questions,
not resolved here.

### Principle alignment

"Judgment in the model, mechanics in scripts" is unchanged by this story: no
check becomes a semantic judgment call; only the vocabulary table and two
check-target lookups move. "Minimize structural drift, prefer reuse over
creation" (`CLAUDE.md`) is why this design edits the existing constants and
lookups in place rather than introducing a second schema, a config file, or a
new script — same file, same functions, same CLI contract, only the mapped
name and grounding-bucket set change. "Nothing signs off on itself" is why
this remains a script comparing structure, not a model asserting a doc
"looks about right."

## User journey

Walks `PRODUCT.md`'s critical user journey 1 (Full cycle), the exact step
this story unblocks:

1. A developer invokes `/design` for a new feature (already implemented,
   sibling story `design-skill`, issue #8). `/design` drafts
   `docs/design/<slug>.md` using the contract's seven section names, per
   that story's own already-ratified fork ruling.
2. `/design`'s Step 5 calls `scripts/design-lint docs/design/<slug>.md`
   before any viva round launches. **Before this story**, this call always
   fails — 14 violations, demonstrated above, against a doc that is, by
   every other measure (content, evidence, a passed human gate on its sibling
   fixtures), well-formed. There is no edit to the draft that escapes this:
   the tool is checking for section names no correctly-authored doc will
   ever carry, so the developer is stuck in a loop `/design`'s own committed
   "fixed and re-linted before Step 6 ever launches a server" behavior can
   never exit.
3. **After this story's build phase lands the remap**, `design-lint` checks
   the same draft against `Problem & persona` / `Proposed design` /
   `User journey` / `Out of scope` / `Alternatives considered` /
   `Operational readiness` / `Open questions`. The same draft that failed
   with 14 violations now passes cleanly — the tool checks for what
   `/design` actually produces.
4. If the draft has a real gap — `Proposed design` reads as pure narrative
   with no concrete file/endpoint/field citations, or `Problem & persona`
   asserts a persona with no `PRODUCT.md`-verbatim quote, no tree-checkable
   citation, and no interview ruling behind it — `design-lint` still reports
   it by name, and `/design` fixes and re-lints before Step 6, exactly as
   the original design-lint story intended. The *guarantee* the tool exists
   to provide is unchanged; only the vocabulary it checks against is
   corrected.
5. Viva review proceeds against a doc `design-lint` has actually validated —
   not one that failed for a reason unrelated to whether it's a good design.

No step of this journey changes shape from what `PRODUCT.md` or the
`design-lint`/`design-skill` design docs already committed to; this story is
what makes the tool those two docs described actually agree with each other.

## Out of scope

- **Check 5's `(qN)` fork-ruling scan** — untouched; it is section-name
  agnostic already, and this story's acceptance criteria names only Checks
  1-4. Whether it still has a real target is flagged in Open questions, not
  fixed here.
- **`DESIGN.md`'s own "Design doc structure" line** — still states the
  handoff-literal `Intent`/`Experience`/`Contracts`/`Approach`/`Assumptions`/
  `Not doing`/`Risks` text this story's own evidence shows no real doc uses.
  `design-skill`'s design doc already flagged this exact staleness in its own
  Open questions. `CLAUDE.md`'s after-each-review table names
  `/deep-review interface` as the mechanism that updates `DESIGN.md`, not
  this story — fixing the doc's prose is a separate, already-tracked
  concern, not a `scripts/design-lint` change.
- **`design-skill`'s implementation, or any further change to
  `skills/design/SKILL.md`** — that story (issue #8) is already built on its
  own sibling branch; this story does not touch it.
- **Verifying `design-lint` against `docs/design/design-skill.md` itself** —
  that file lives on branch `epic/m2-design-skill--design-skill`, a sibling
  branch this design phase does not touch (worker-contract's "one phase, one
  story, one worktree"). The acceptance criteria's closing demonstration
  ("running the patched linter against `design-skill`'s own
  `docs/design/design-skill.md` exits 0 clean") is the build phase's
  verification step, not something available to prove from this worktree
  today.
- **New checks beyond the four being remapped, or coverage for anything
  `reference/design-doc-contract.md` doesn't itself require** — this story
  reconciles an existing 1:1 set of checks onto an existing set of names; it
  does not expand what gets checked.
- **Wiring `design-lint` into CI** — matches `CLAUDE.md`'s own note that Ruff
  itself isn't wired into CI yet; a separate, unscoped concern, and already
  out of scope for the original design-lint story this one reconciles.
- **Any change to `scripts/plan-lint`, `PLAN.md`, or M3's `/plan` skill** —
  unrelated sibling surface.

## Alternatives considered

1. **Accept both vocabularies — add the contract's seven names as a second,
   parallel schema alongside the existing `DESIGN.md`-sourced one.**
   Rejected: doubles the surface area for exactly the ambiguity this story
   exists to remove, and only one of the two schemas — the contract's — has
   ever been used by a real, gate-reviewed doc in this repository.
   `CLAUDE.md`'s "prefer deletion over addition" argues directly against
   carrying a second vocabulary nothing has ever needed.
2. **Fix `DESIGN.md` instead of `scripts/design-lint`** — have `/design`
   draft docs using `Intent`/`Experience`/`Contracts`/`Approach`/
   `Assumptions`/`Not doing`/`Risks`, matching the linter as it stands today.
   Rejected on the evidence: this would mean retitling six already-shipped,
   already-gate-design-reviewed docs' headings (or accepting they were wrong
   all along) to match a stub-era guess `DESIGN.md`'s own header admits is
   "still extracted from the... handoff document, not from running code."
   `design-skill`'s own design doc already ruled this fork the other way,
   through a passed `/gate-design-review` — reopening it here would
   relitigate an already-decided question this story's acceptance criteria
   doesn't ask it to touch.
3. **Drop the closed-vocabulary heading check entirely** — since
   `reference/design-doc-contract.md` itself says "sections may carry any
   heading text as long as the content answers the mapped question," make
   Check 1 a pure count check (any 7 headings, any names). Rejected: that
   flexibility is stated for the human product-reviewer gate reading for
   substance; a mechanical script cannot judge substance, only structure.
   Dropping the closed-vocabulary check would let `design-lint` pass a doc
   with seven arbitrarily-named sections that answer none of the contract's
   six questions — exactly the "passes checks that don't actually enforce
   anything" failure mode this epic's own pre-mortem (risk #1) names.
4. **Retain the old required/optional split, mapped onto three of the new
   seven names, leaving the other four optional.** Rejected:
   `reference/design-doc-contract.md`'s own table has no optional row to map
   that distinction onto — inventing one where the source draws none would
   itself be "inventing schema details beyond `DESIGN.md`'s Formatting
   section + `design-doc-contract.md`," the exact failure mode epic
   pre-mortem risk #1 names by name.
5. **Map Check 3's checkability semantic onto `Open questions`** (the old
   `Assumptions`/`Risks` handoff-era names both land there in
   `design-skill`'s own loose correspondence table). Rejected on inspection
   of that table's own caveat ("approximate correspondence, for
   traceability... not a literal per-cell mapping") and of the actual
   content: `reference/design-doc-contract.md` defines `Open questions` as
   *unresolved* decisions ("an empty section is fine; a missing one hides
   risk") — requiring every bullet there to be checkable would be backwards,
   penalizing the section for doing its job. `Problem & persona`'s own
   contract text ("verbatim, not a paraphrase") is the direct semantic
   match, confirmed by both real fixtures' own blockquote pattern.

## Operational readiness

Same class of change as the original design-lint story: `scripts/design-lint`
is a one-shot local CLI script, no deployed service, no data migration.

- **Rollout**: in-place edit of `scripts/design-lint`'s constants
  (`CANONICAL_SECTIONS` and the two check-target lookups in
  `check_2_contracts_concrete`/`check_3_assumptions_checkable`, renamed to
  match) and `find_section` call sites. Same file, same CLI shape, same
  0/1/2 exit-code contract. No feature flag, no staged rollout.
- **Rollback**: `git revert` the commit. `design-lint` is already called from
  `/design`'s Step 5 on the sibling `design-skill` branch (not yet merged to
  `epic/m2-design-skill` as of this story's design phase) — once that branch
  merges, a revert of this story restores the prior, already-broken-against-
  every-real-doc behavior. That is a known regression, not a neutral no-op;
  worth naming explicitly in the revert commit message if this is ever
  exercised after both stories have merged.
- **Failure visibility**: unchanged. Every violation is still printed by
  name; the exit code is still non-zero on any failure; a clean pass still
  prints a short confirmation line.
- **Tests**: `tests/test_design_lint.py`'s existing fixtures (`CLEAN_DOC`,
  `OUT_OF_RANGE_COUNT_DOC`, and every violation-case test named after the old
  section names) are updated to the seven new names and the `== 7` exact-count
  rule in place of the `[5, 8]` range. New fixtures cover each remapped
  check's new mechanism: a `Problem & persona` asserting a persona with no
  `PRODUCT.md`-verbatim blockquote, no tree-checkable path citation, and no
  `(qN)` ruling (Check 3's new target); a `Proposed design` that is prose-only
  or short of the artifact-span floor (Check 2's new target, same threshold
  mechanic, new section); and a `User journey` with no failure-path language
  (Check 4, same mechanism, renamed section — this fixture is a rename of the
  existing `Experience` case, not new logic). Run via `uv run --no-project
  python3 -m unittest discover -s tests -v`, matching this repo's existing
  test convention (`CLAUDE.md`).
- **Acceptance demonstration**: this story's acceptance criteria closes on
  "running the patched linter against `design-skill`'s own
  `docs/design/design-skill.md` exits 0 clean." That demonstration runs in
  the build phase, against the real file on the sibling `design-skill`
  branch, once both branches can be reconciled onto a shared tree — it is
  named here as the concrete verification step the build phase must
  actually run and capture as evidence, not asserted as already done.

## Open questions

- **Whether Check 5's `(qN)` fork-citation convention still has a real
  target.** `design-skill`'s own already-ratified design doc presents forks
  via a `**Fork: ...**` / options-table / `**(recommended):** <option>`
  convention (`docs/design/design-skill.md`'s own Step 4 and Out of scope
  sections, on the sibling branch), not inline `(qN)` tags — meaning Check 5
  may be vacuously passing (zero `(qN)` tags found, zero violations reported)
  against every real doc this convention would actually need to check. This
  story's acceptance criteria names only Checks 1-4 for remapping; Check 5's
  own fate is flagged here, matching this project's own precedent
  (`docs/studious/premortems/design-lint.md`, risk #1) of surfacing drift
  explicitly rather than silently folding it into a different story's scope.
- **Whether `DESIGN.md`'s "Design doc structure" line should be corrected**
  to state the contract's seven names once this story lands, so a future
  reader isn't misled by text this design doc's own evidence already shows
  is stale. Left to `/deep-review interface`, per `CLAUDE.md`'s own
  review-cadence table, not this story.
- **Whether the concreteness floor (`MIN_ARTIFACT_SPANS`, currently 3) should
  change now that Check 2 targets `Proposed design`** — typically a longer,
  richer section than the old narrow `Contracts` section was. This design
  proposes keeping the existing floor as the build-phase default (it already
  passes against `docs/design/design-lint.md`'s own `Proposed design`
  section, which is dense with qualifying spans) but leaves the exact number
  a build-phase constant, per `reference/design-doc-contract.md`'s own
  non-requirements clause and this project's established precedent
  (`docs/design/design-lint.md`'s own Open questions) of not fixing such
  constants at design time.
- **Whether all three of Check 3's grounding buckets should carry equal
  weight**, or whether a `Problem & persona` section should be required to
  use the `PRODUCT.md`-verbatim blockquote specifically (bucket c) rather
  than accepting a tree-checkable citation or interview ruling alone. This
  design proposes accepting any of the three (generalizing Check 3's
  original either/or shape), but the precise acceptance logic — e.g. whether
  a section with only a premortem-doc citation and no persona blockquote at
  all should still pass — is a build-phase mechanic, not fixed here.
- **Whether Check 1 should permit an eighth section beyond the seven
  (`reference/design-doc-contract.md` itself doesn't explicitly forbid one)**
  for a case like an unusually long `Operational readiness` needing its own
  split-out appendix. This design keeps the exact-seven rule because both
  real fixtures satisfy it without exception and the contract names no
  eighth consumer to justify one; a real future doc that needs an eighth
  section would expose a gap this doc hasn't resolved.
