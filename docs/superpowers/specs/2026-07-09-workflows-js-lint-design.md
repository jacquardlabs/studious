# Design: Add a JS linter and CI job for workflows/

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Story:** workflows-js-lint (epic: gate-ledger-robustness)
**Source:** [#103](https://github.com/jacquardlabs/studious/issues/103)

## Problem & persona

The persona is PRODUCT.md's secondary persona: **"the maintainer dogfooding Studious
on Studious."** Their job-to-be-done is keeping the plugin's own delivery tooling under
the same rigor the plugin prescribes to everyone else — PRODUCT.md's known problem #24
names this directly: **"the entire system is markdown prompts, but CI only cuts
releases: no markdown lint, no plugin-schema validation, no link-check that referenced
agents/skills exist, no golden-fixture behavioral tests. Gate-contract regressions are
caught only by manual audit."** That gap has been closing job by job — bash gets
`shellcheck`, Python gets `pytest`, markdown gets `markdownlint-cli2` — but
`workflows/epic-driver.js`, the ~450-line `/work-through` scheduler that CLAUDE.md
names as one of the two places **"code owns bookkeeping"** (the other is
`bin/gate-ledger`), ships with `node --check` as its only automated check.

`node --check` only proves the file parses; it asserts nothing about the shape of the
code. Three audit rounds on the branch that built `/work-through` caught real defects
by eye that a linter would catch mechanically: an index computed after a `.filter()`
call being read against a different, unfiltered array (index-misalignment on dead
agents); three sequential `.unshift()` calls that silently reversed the intended
display order (unshift-ordering); and a boolean derived from a dispatch result that can
come back `null` (an agent died), used to decide whether to escalate, without the died
case ever being checked (fail-open null handling). None of these are syntax errors —
`node --check` passed on every one of them.

Confirmed while grounding this design: `node --check`'s protection on this specific
file is thinner than it looks. `workflows/epic-driver.js` opens with `export const
meta` (module syntax the harness reads for metadata) and ends with a bare top-level
`return {...}` — legal only because the Workflow harness wraps the body in an async
function of its own before executing it. `node --check workflows/epic-driver.js`
exits 0 today, but only because the repo has no `package.json` anywhere in this file's
directory ancestry, which routes Node into a lenient ambiguous-module-type path; adding
a `package.json` for an unrelated reason anywhere above `workflows/`, or moving the
file, would very plausibly flip that and either break the check on valid code or stop
validating anything. The one automated gate this file has is an accident of the repo's
current shape, not a guarantee — and it never checked logic shape to begin with.

## Proposed design

Add ESLint, scoped to `workflows/**/*.js`, invoked the same way the repo already
invokes `markdownlint-cli2` and `shellcheck`: a single pinned version fetched ad hoc via
`npx` in CI, no `package.json`, no committed `node_modules` — the plugin repo takes on
no new dependency footprint. The config lives in one file at the repo root
(`eslint.config.mjs`, flat config, scoped by a `files` glob rather than by directory
placement) so it is auto-discovered without a `-c` flag and naturally covers any future
file dropped into `workflows/` — the issue's own framing is "before a second workflow
script lands."

The rule set has two layers:

**A generic correctness floor** — a small, hand-picked set of ESLint's built-in rules
(unused variables, unreachable code, unsafe negation/optional-chaining, duplicate keys/
args, `no-fallthrough`, `no-constant-condition`, and so on) plus explicit declarations
of the five globals the Workflow harness injects at call time (`args`, `agent`,
`parallel`, `log`, `phase`) so that `no-undef` still catches a real typo — the one class
of defect `node --check` is structurally unable to see, because the file has no module
system to catch a misspelled identifier against. This layer needs no shareable config
or plugin; it is a deliberate hand-picked list, not `eslint:recommended`, so the rule
surface stays exactly as wide as the failure classes being defended against and nothing
wider.

**Three rules targeted at the three named defect classes**, each traced to the commit
that actually fixed its historical instance:

- *Index-misalignment on dead agents* (fixed by the `joinReports` rewrite that replaced
  a `reports.filter(Boolean).map((r, i) => ...)` pattern): a rule flags any
  `.filter().map()` chain whose `.map()` callback takes an index parameter — exactly the
  shape that lets a post-filter index drift out of alignment with a parallel,
  unfiltered array.
- *Unshift-ordering* (fixed by collapsing three sequential `parkedThisRun.unshift(...)`
  calls, which silently reversed the intended order, into building the ordered list
  first and unshifting it once via spread): a rule flags any bare, non-spread
  `.unshift()` call.
- *Fail-open null handling* (the class behind a pre-mortem-escalation fix that never
  shipped to `main` — see Open Questions): a rule flags a `const flag = x && ...`
  boolean declaration whenever `flag` is never referenced in negated form (`!flag`)
  anywhere in scope — the shape that let a died/absent dispatch collapse into the
  same value as an explicit negative result, with nothing downstream distinguishing
  "checked and clear" from "never checked."

A working prototype confirms the mechanism end to end, with zero new dependencies:
because the file mixes top-level `await` (module-only) with a top-level `return`
(function-body-only), no single ESLint parser goal accepts it as-is, so the config
lints the file in the same async-function shape the harness actually executes it in —
stripping the one `export` keyword the harness itself consumes and wrapping the
remainder in an async function before parsing, entirely with stock ESLint (no custom
parser, no extra package). Against the real file, the two structural rules (index-
misalignment, unshift-ordering) come back clean, and against reconstructions of both
historical bugs, both fire correctly.

The third rule is coarser by nature: it cannot distinguish a flag checked via literal
`!flag` from one whose falsiness is instead handled implicitly (fed into a
`Boolean(...)` value the caller inspects, e.g. `ready: Boolean(auditOk && shipOk &&
readyRecorded)`). Run against the real file, it currently flags two such flags
(`auditOk`, `shipOk`) that are, on inspection, already fail-closed — just not via
literal negation. Rather than loosen the rule (and lose its ability to catch a real
recurrence) or drop it from the config (and fail the acceptance criterion that all
three classes are covered), the design keeps it at full strength and treats those two
sites as the documented suppressions the acceptance criteria already anticipates: each
gets an inline suppression comment carrying a one-line `// fail-closed: <why>`
justification, in the same comment-driven-safety idiom this file already uses
everywhere (`shellSafe`, `joinReports`, `mergeSem` are each preceded by a prose comment
explaining a non-obvious invariant). The rule's imprecision becomes a forcing function:
every nullable-dispatch boolean in the file must be actively justified in writing at
the point it's introduced — which is the exact discipline whose absence let the
original bug ship unnoticed.

**CI job.** A fifth parallel job alongside `markdown`, `python-checks`, `ledger`, and
`shellcheck` in `.github/workflows/ci.yml`: `node --check` over every file in
`workflows/`, then the pinned ESLint invocation over the same set. Mirroring the
existing four jobs, it runs on every push/PR rather than path-filtered — none of the
current jobs are path-scoped either, and the cost of an always-on job here is a few
seconds against a single small directory.

## User journey

This does not touch any of PRODUCT.md's three numbered user journeys (init, per-feature
gate, per-project review) — it extends the secondary persona's own journey of
maintaining Studious under its own discipline, the one that motivated known problem #24
and every existing CI job.

Before: the maintainer (or a dispatched worker, since `/work-through` is itself
building against this file) edits `workflows/epic-driver.js`, pushes, and CI runs
`markdownlint`, the Python link-checker and schema validator, the gate-ledger bash
tests, and `shellcheck` — none of which touch the one file that schedules the fully
autonomous epic-driving path. A logic defect in the scheduler ships silently unless a
human happens to catch it by eye, which is exactly what happened three times on the
branch that built this file.

After: the same push additionally runs `node --check` (parseability) and ESLint
(the three named defect shapes, plus the generic floor) against every file in
`workflows/`. A reintroduction of any of the three historical shapes fails CI before
merge, the same way a `shellcheck` regression in `bin/gate-ledger` already does. A
second workflow script, whenever one lands, is covered automatically by the same
`files` glob with no config change.

## Out of scope

- **Fixing any defect the new lint surfaces beyond adding the two required
  suppression-justification comments.** In particular: tracing the fail-open rule's
  intended target turned up evidence that the actual pre-mortem-escalation fail-closed
  fix for this defect class was built on an exploratory branch (`feat/work-through`)
  that never merged to `main` — the live `workflows/epic-driver.js` today fetches the
  pre-mortem verifier's findings but does not escalate on a REALIZED or died verifier
  the way its `auditOk`/`shipOk` siblings do. That is a real scheduler defect, not a
  linting concern, and this epic already carries a dedicated story for it
  (premortem-hook-awareness, #100). This story adds the tool that would have caught it
  faster; it does not fix it.
- **A shareable config or plugin** (`eslint:recommended`, `eslint-plugin-unicorn`,
  Biome, etc.). Deliberately out — see Alternatives considered.
- **Formatting/style enforcement.** This is a correctness lint scoped to the three
  named failure classes plus a small generic floor, not a style tool — mirrors the
  markdown job's own choice to ratchet current state rather than fight prose style.
  Prettier or an ESLint style ruleset is a separate concern from a separate issue, if
  ever.
- **Any other JS in the repo.** There is none outside `workflows/`; the `files` glob
  stays scoped there rather than to the whole repo.
- Per PRODUCT.md's "What we're NOT building": this remains a check that reports (via CI
  exit status), never a tool that reformats or auto-fixes code in place.

## Alternatives considered

**Biome instead of ESLint.** Rejected: Biome does not expose ESLint's
`no-restricted-syntax` arbitrary-AST-selector escape hatch, which is what makes two of
the three targeted rules possible without hand-writing and maintaining a custom plugin
package. ESLint's built-in escape hatches keep the whole config to one dependency-free
file.

**Pull in `@eslint/js`'s `recommended` config (or a plugin like `eslint-plugin-unicorn`)
instead of hand-picking rules.** Rejected for now: resolving a shareable config through
an ad-hoc `npx` invocation means fetching and aligning multiple packages instead of one,
more moving parts than the repo's existing pinned-single-package convention
(`markdownlint-cli2@0.23.0`, `shellcheck v0.11.0`) uses elsewhere, and a broader
"recommended" rule surface would flag stylistic patterns (dense one-line arrow
functions, for one) that this file uses deliberately and that have nothing to do with
the three defect classes this story exists to catch. A hand-picked list keeps the
surface exactly as wide as the problem.

**TypeScript with `checkJs`/JSDoc types instead of ESLint.** Rejected: heavier tooling
for one ~450-line script, and — checked directly against the fail-open defect —
`strictNullChecks` would not have caught it anyway. The original bug's nullable access
was already guarded (`premortem && ...`); the defect was that the *absent* case was
never escalated, which is a business-logic gap a type checker has no way to see.

**Leave `node --check` as the only automated gate and rely on audit-by-eye.** Rejected:
this is the status quo issue #103 exists to close. Audit-by-eye already missed all
three defect classes at least once each before they were caught and fixed.

## Open questions

- **Calibration of the fail-open rule.** Is treating `auditOk`/`shipOk` as documented
  suppressions (forcing a written fail-closed justification) the right acceptance
  outcome, or should `/gate-design-review` push for a tighter heuristic before this
  ships? The rule's imprecision is a known, tested property of this design, not an
  oversight — flagging it explicitly for that gate's judgment.
- **The live pre-mortem escalation gap.** Noted under Out of scope for
  premortem-hook-awareness (#100) to pick up; flagged here so it isn't lost between
  stories.
- **Exact ESLint version to pin.** The prototype validated against the current latest
  (10.6.0) at design time; build should pin whatever is current and stable then,
  mirroring the repo's existing pinned-tool convention, and record the pin in the CI
  YAML the same way the other four jobs do.
- **Path-filtering the CI job.** The design defaults to always-on (matching the other
  four jobs, none of which are path-scoped); if CI runtime becomes a concern later, a
  `paths:`-filtered variant is a small follow-up, not a blocker here.
