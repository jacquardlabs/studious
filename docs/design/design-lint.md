# Design: design-lint (mechanical validator for design docs)

## Problem & persona

Primary persona, verbatim from `PRODUCT.md`:

> A developer using Claude Code, likely already pairing it with studious's
> judgment gates, who wants a repeatable, verifiable build/implementation
> workflow instead of ad hoc prompting or Superpowers.

That persona's problem today (this story, issue #9): `scripts/design-lint` is still the M1 stub —
it "exits 0 unconditionally... so it's safe to wire into a build/CI step
ahead of the real implementation" (its own docstring). Once the sibling
story `design-skill` (issue #8/#10, this same epic) starts producing real
`design-<slug>.md` documents from a batch interview, nothing mechanically
confirms the doc obeys `DESIGN.md`'s own "Design doc structure" convention
before a human or a viva review session spends a cycle on it. That
convention isn't decoration: `PRODUCT.md`'s critical user journey 1 routes
`/design`'s output straight into studious's `/gate-design-review`, and this
project's own principle "Nothing signs off on itself" says the model must
not be the one attesting the doc is well-formed — a script must. This is
the same gap `evidence-capture`/`status-flip`/`verify` closed for `/build`
at M4 (issue #14 lineage): a stub that always passes is structurally
indistinguishable from "no check ran at all," and every cycle it stays a
stub, a malformed `design-<slug>.md` can reach a human reviewer (or viva)
with, for example, a fork the interview raised but never actually ruled on,
silently dropped rather than surfaced.

**This design doc is deliberately narrow about where its checks' concrete
shapes come from**, because this epic's own pre-mortem
(`docs/studious/premortems/m2-design-skill-epic.md`, risk #1) names the
exact failure mode to avoid: `design-lint` and `design-skill` are sibling
stories with no dependency edge between them, and if either "invents schema
details beyond `DESIGN.md`'s Formatting section + studious's
`design-doc-contract.md`," `design-skill`'s real output could fail
`design-lint`'s real checks, or worse, pass checks that don't actually
enforce anything. Every check below is sourced from exactly two places: (1)
`DESIGN.md`'s own "Design doc structure" line (5-8 sections, each tied to a
named downstream consumer: Intent, Experience, Contracts, Approach,
Assumptions, Not doing, Risks), and (2) the one real `design-<slug>.md` this
project has ever produced — `docs/jig/dogfood/design-viva-unified-session.md`
on branch `docs/m0-paper-dogfood` (the M0 paper dogfood of `/design` against
viva issue #109, predating any jig code). Nothing here is invented beyond
those two sources; where they don't fully specify a mechanic, that gap is
named explicitly in Open questions rather than papered over.

## Proposed design

`scripts/design-lint` replaces its stub body in place (same file, same CLI
shape as `plan-lint`/`verify`/`evidence-capture` — a single Python
executable, no new file, per this story's own acceptance criteria). Given a
path to a `design-<slug>.md` file, it parses the document's top-level (`##`)
sections and runs five independent checks, one per this story's acceptance
criteria. It reports **every** violation found in a single run — not just
the first — naming the specific missing element for each, then exits
non-zero if any check failed, or zero with a short confirmation if all five
passed. Reporting every violation per run (rather than failing fast on the
first) matches `verify`'s own established precedent: "per-item results are
always reported, even on an overall PASS," so a human fixing a doc doesn't
have to re-run the linter once per violation.

**Section-parsing convention.** A trailing `## Revision History` section,
separated from the design content by a `---` divider, is excluded from
every check below. This is an existing convention, not new: both
`docs/design/finish-skill.md` and the dogfood fixture end this way (a viva
sign-off stamp appended after the design content proper), and viva's own
section-counting for review purposes is a separate concern from what
`design-lint` checks.

### Check 1 — Section count and vocabulary

Top-level sections (excluding Revision History) must number **5-8**, and
every heading (case-insensitive, whitespace-normalized) must be drawn from
`DESIGN.md`'s own named list — the only canonical vocabulary this repo has
committed to today: `Intent`, `Experience`, `Contracts`, `Approach`,
`Assumptions`, `Not doing`, `Risks`. No duplicates. A heading not on this
list fails by name ("section '\<heading\>' does not match jig's canonical
section vocabulary — see `DESIGN.md`'s Design doc structure"); a count
outside 5-8 fails by number ("N top-level sections found; `DESIGN.md`
requires 5-8").

Since checks 2-4 below presuppose the `Contracts`, `Assumptions`, and
`Experience` sections exist, those three are unconditionally required; the
remaining four canonical names (`Intent`, `Approach`, `Not doing`, `Risks`)
fill out the 5-8 range, with at least two of the four present to reach the
floor of 5. (The dogfood fixture — the one real example available — carries
all seven, which trivially satisfies this.)

### Check 2 — Contracts section is concrete, not prose-only

"Concrete/checkable shapes, not prose only" is operationalized as: the
`Contracts` section must contain at least one shape-marker — a fenced code
block, a markdown table, or a minimum count of distinct inline-code spans
(`` `token` ``) naming concrete artifacts (a filename, an endpoint, a field).
A section with zero such markers fails, naming the section. This is
grounded directly in the dogfood fixture's own `Contracts` section, which
is dense with backtick-quoted names (`` `answers.json` ``,
`` `POST /handoff {url}` ``, `` `server.py:3120-3134` ``) precisely because
that's how a human writer already expressed "concrete, not prose-only"
before `design-lint` existed to check it mechanically. The exact minimum
count is a build-phase constant (see Open questions), not fixed here — the
design commitment is "some machine-checkable marker of concreteness," not a
specific number.

### Check 3 — Assumptions are checkable against the actual tree

Every bullet in the `Assumptions` section must be checkable one of two ways,
matching the two patterns the dogfood fixture already demonstrates:

1. **Interview-ruled** — tagged with the fork-reference convention Check 5
   also reads (see below), whose ruling is recorded (in which case Check 5
   already validates it; Check 3 only confirms the tag is present).
2. **Tree-checkable** — citing a real path in the actual repository, as an
   inline-code span shaped like a file path (optionally with a `:line` or
   `:line-line` suffix, matching the dogfood fixture's own
   `` `server.py:3120-3134` `` shape). `design-lint` resolves the path
   portion against the real checkout at lint time; a citation to a path that
   doesn't exist fails by name, quoting the offending bullet and the
   unresolved path.

A bullet satisfying neither pattern is the violation this check exists to
catch — reported by its own bullet text (or line number), not a generic
"assumptions section failed." This directly operationalizes "checkable
against the actual tree": for the tree-checkable pattern, `design-lint`
does not trust the prose — it opens the file.

### Check 4 — Experience covers at least one failure path

The `Experience` section must name at least one failure path alongside its
happy-path content — checked as: the section's text contains at least one
recognizable failure-signaling token from a small fixed vocabulary (e.g.
"if ... fails", "error", "stops", "refuses", "not installed", "unavailable",
or a `Failure` sub-heading — exact list a build-phase constant). A purely
happy-path `Experience` section with no failure-shaped language at all fails,
naming the section.

### Check 5 — Every fork has a recorded ruling

Forks raised during the batch interview step are referenced inline via the
`(qN)` convention — the one precedent this project has (the dogfood
fixture's own `(q1)` through `(q7)` citations, e.g. "`.brainstorm-patch-
version` retirement is explicitly **not** part of this contract (q4)").
`design-lint` scans the whole document (not just one section, since the
dogfood fixture's forks are referenced across `Intent`, `Contracts`,
`Assumptions`, and `Not doing` alike) for every distinct `(qN)` tag, and
requires a ruling-shaped clause in the same sentence or bullet — a small
fixed vocabulary of ruling verbs (e.g. "ruled", "confirmed", "rejected",
"decided", "ranked" — exact list a build-phase constant, not fixed here). A
`(qN)` reference with no adjacent ruling language fails by number, naming
which fork (`q<N>`) has no recorded ruling.

**This check is the direct instantiation of epic pre-mortem risk #1.** The
`(qN)` convention is *proposed* here, sourced from the only real precedent
available — it is not a contract `design-skill` has itself committed to,
because `design-skill` hasn't been designed yet. See Open questions.

### Principle alignment

"Judgment in the model, mechanics in scripts" is why every check above is a
structural/pattern match (heading names, counts, path existence, a fixed
token vocabulary) rather than a semantic judgment call ("is this a *good*
ruling?") — that judgment stays with the viva reviewer and studious's
`/gate-design-review`, never with this script. "Nothing signs off on
itself" is Check 3's whole reason for opening files instead of trusting
prose. "Recommend one action; the human decides" shapes the report-all
(never auto-fix) posture: `design-lint` names every violation and stops;
it never rewrites the doc.

## User journey

Walks `PRODUCT.md`'s critical user journey 1 (Full cycle), the step this
story adds between `/design`'s drafting and its viva review:

1. The developer runs `/design` (once `design-skill` ships). The batch
   interview raises three forks; all three get a ruling recorded inline
   during the interview.
2. `/design` drafts `design-<slug>.md` from the interview answers. Before
   (or as part of) handing the draft to viva for review, `design-lint` runs
   against it.
3. The draft is missing a ruling for one fork (a `(q2)` tag with no
   adjacent ruling language, dropped during drafting) and its `Contracts`
   section is pure prose (no backtick-quoted names at all). `design-lint`
   exits non-zero, naming both: "fork q2 has no recorded ruling" and
   "section 'Contracts' has no concrete shape markers." No human or viva
   cycle is spent reviewing a doc with these gaps.
4. The developer (or the drafting step) fixes both — adds the dropped
   ruling, adds concrete artifact names to `Contracts`. `design-lint` runs
   again and exits 0 clean.
5. Viva review proceeds against a doc `design-lint` has already confirmed
   is structurally complete — the reviewer spends its cycles on substance
   (is this the right design?), not on catching a dropped fork or a vague
   contract that a script could have caught for free.

No step of this journey changes shape from what `PRODUCT.md`/`DESIGN.md`
already committed to; this story is the first thing that actually
mechanizes the check `DESIGN.md`'s "Design doc structure" line describes.

## Out of scope

- **The `/design` skill itself** (sibling story `design-skill`, issue
  #8/#10) — this story only builds the linter. It does not implement the
  batch interview, forking, or viva-review orchestration that produces the
  document `design-lint` checks, and does not decide whether `/design`
  calls `design-lint` automatically as a step or leaves it a standalone
  script a human/CI runs (that wiring decision belongs to `design-skill`'s
  own design).
- **Auto-fixing a deficient doc.** `design-lint` reports; it never rewrites
  the document, matching `plan-lint`/`verify`'s own report-only stance.
- **Judging content quality** beyond structural/mechanical markers — whether
  an assumption's ruling was the *right* call, or whether a `Contracts`
  shape is actually correct, stays with the viva reviewer and
  `/gate-design-review`, not a mechanical script.
- **Committing to the `(qN)` fork-citation convention as `design-skill`'s
  own contract.** This doc proposes it (see Check 5); ratifying it as
  `design-skill`'s actual interview-output shape is that sibling story's
  decision, not this one's.
- **Exact regex/threshold constants** (minimum inline-code-span count, the
  closed ruling-verb and failure-token vocabularies) as literal code — named
  at the behavior level here; left to the build phase per
  `reference/design-doc-contract.md`'s own non-requirements clause.
- **CI wiring** — matches `CLAUDE.md`'s own note that Ruff itself isn't
  wired into CI yet; a separate, unscoped concern.
- **Any change to `scripts/plan-lint`'s existing stub behavior.**

## Alternatives considered

1. **A model call to judge doc quality semantically** ("is this ruling
   good?", "is this section concrete enough?") instead of pattern-based
   mechanical checks. Rejected: `design-lint` is a script; per "Judgment in
   the model, mechanics in scripts," a script that needs a live model call
   to decide pass/fail isn't a script, it's the judgment step wearing a
   script's clothes — and it would no longer be something viva or a human
   reviewer could trust as an independent, repeatable check.
2. **Fail-fast on the first violation** instead of reporting every
   violation found. Rejected: matches `verify`'s own precedent of reporting
   per-item results even on an overall pass, so a human fixing multiple
   issues doesn't re-run the linter once per issue.
3. **Requiring literal fenced JSON-schema blocks in `Contracts`** (a strict
   reading of "concrete shapes"). Rejected: this would fail the one real
   precedent this project has — the dogfood fixture's `Contracts` section
   uses backtick-quoted names and paths, not JSON schema blocks. The
   inline-code-span heuristic is the more inclusive proxy that still
   excludes prose-only sections.
4. **Treating all seven canonical names as unconditionally mandatory** (no
   5-8 range, always exactly 7). Rejected: contradicts `DESIGN.md`'s own
   explicit range language — if all seven were mandatory, `DESIGN.md` would
   say "7 sections," not "5-8."

## Operational readiness

`scripts/design-lint` is a one-shot local CLI script, same class as
`plan-lint`/`verify`/`evidence-capture` — no deployed service, no data
migration.

- **Rollout**: replaces the stub's body in place, same file
  (`scripts/design-lint`), same CLI shape convention as its siblings. No
  feature flag, no staged rollout — matches this story's own acceptance
  criteria ("Replaces the existing stub in place... not a new file").
- **Rollback**: `git revert` the commit that replaces the stub body.
  Nothing else in the repo currently calls `design-lint` (it's not yet
  wired into `/design`, `/gate-design-review`, or CI), so a revert has no
  ripple.
- **Failure visibility**: every violation is printed by name (which check,
  which specific section/bullet/fork); the exit code is non-zero if any
  check failed. A clean pass exits 0 with a short confirmation line, the
  same "stub"-style single print-line convention `design-lint`/`plan-lint`
  already use, now reporting a real result instead of an unconditional
  stub message.
- **Tests**: `tests/test_design_lint.py`, mirroring
  `tests/test_evidence_capture.py`'s style — one fixture per violation
  (missing section, out-of-range count, unrecognized heading, prose-only
  Contracts, an unresolvable path cited in Assumptions, a purely
  happy-path Experience, an unruled fork) plus one conformant clean-pass
  fixture, run via `uv run --no-project python3 -m unittest discover -s
  tests -v` per this repo's existing test convention.

## Open questions

- **The real handoff §5.1 section→consumer table** `DESIGN.md` cites isn't
  available anywhere in this repo. This design commits only to the seven
  names `DESIGN.md` states verbatim. If `design-skill`'s own design/build
  phase surfaces additional canonical names or a different consumer
  mapping, `design-lint`'s canonical vocabulary constant needs a follow-up
  patch — flagged, not resolved here. This is exactly epic pre-mortem risk
  #1; the detection hint asks that `design-skill`'s own real output be run
  through this landed `design-lint` before that story's audit, and that
  check should confirm this open question didn't silently diverge.
- **Whether `(qN)` is really `design-skill`'s committed fork-citation
  convention**, or just this one paper-dogfood author's shorthand. Proposed
  here as the canonical shape because it's the only real precedent that
  exists; not confirmable against `design-skill`, a sibling story not yet
  designed.
- **Exact numeric thresholds and closed vocabularies** (minimum inline-code
  span count for Check 2; the ruling-verb list for Check 5; the
  failure-token list for Check 4) — left to the build phase per
  `reference/design-doc-contract.md`'s own non-requirements clause.
- **Whether a bullet with neither an interview tag nor a tree-checkable
  path should be an automatic Check-3 failure, or whether some assumption
  categories are legitimately neither** (e.g., a pure UX judgment call ruled
  by taste rather than interview or tree fact). This design assumes every
  assumption bullet falls into one of Check 3's two buckets; the one real
  fixture available happens to confirm this, but a genuinely third-category
  assumption would expose a gap this doc hasn't resolved.
