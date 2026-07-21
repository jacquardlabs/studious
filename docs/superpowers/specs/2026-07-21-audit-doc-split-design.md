# Split gate-audit.md's compile-time rules into reference/audit-compilation.md

**Date:** 2026-07-21
**Status:** Design, pre-implementation
**Source:** [#159](https://github.com/jacquardlabs/studious/issues/159), story `audit-doc-split`
of epic `perf-audit-followups`

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features with
Claude Code who wants product judgment and quality gates woven into the build, without
heavy process."** This persona pays the cost this story targets on every `/work-through`
audit round.

`commands/gate-audit.md` is 189 lines / 28,049 bytes and serves two readers with almost no
overlapping need: an interactive session running `/gate-audit` directly (dispatch
mechanics — which auditors run, routing/skip rules, shared-contract assembly, re-audit
narrowing), and a compile-only reader that only needs the last ~40 lines (severity mapping,
lane-state rules, the critical-challenge process, verdict tiers). `workflows/epic-driver.js`'s
`auditFanIn()` is that second reader, and it pays for the whole file anyway — its prompt
opens with "Read commands/gate-audit.md from the plugin root ... and apply ITS compilation
rules and severity rubric to the auditor reports below." A freshly dispatched compiling
agent, which never saw the auditors dispatched and has no other route to the compile rules,
must open and read the entire 28,049-byte file to reach the 7,823-byte (48-line) "## After
all auditors return" section it actually applies — paying for the other ~72% (dispatch
mechanics: shared-contract assembly, diff precompute, evidence-log resolution, re-audit-scope
narrowing, the 13 numbered auditor role descriptions, changeset-routing prose) every time.

`auditFanIn()` is the sole compile step behind both `auditRound()` (every story's audit
round, including every `FIX AND RE-AUDIT` retry up to `MAX_FIX_CYCLES`) and
`finaleAuditRound()` (the epic finale) — confirmed at call sites
`workflows/epic-driver.js:680` and `:974`. `/gate-audit`'s own interactive session never
incurs this specific cost (it's already executing `gate-audit.md`'s text as its own running
instructions, not issuing a second `Read` from inside a freshly dispatched agent) — the
waste is entirely on the epic-driven path, and it recurs on the single highest-frequency
compile-agent dispatch `epic-driver.js` makes.

PRODUCT.md's secondary persona, **"the maintainer dogfooding Studious on Studious,"** is who
filed this: issue #159, "Independent performance audit of `main` (2026-07-20)," cross-referenced
against #130 (the epic's own originating cost audit).

## Proposed design

One relocation, two pointer edits, one vocabulary unification. No new mechanism, no auditor
behavior change, no verdict-token change — per the epic's own boundary: "without changing
any gate's judgment, only its cost or visibility."

### 1. New file: `reference/audit-compilation.md`

Move `gate-audit.md`'s entire `## After all auditors return` section (lines 112–159)
verbatim, following this repo's existing "consult it, don't restate it" convention
(`reference/severity-rubric.md`, `reference/audit-routing-signals.md`,
`reference/gate-vocabulary.md`), with these edits to make the text serve both callers
correctly rather than reading as though written for only one:

- **Name both callers at the top**, the way `reference/severity-rubric.md`'s own opening
  line does ("`commands/gate-audit.md` cites this file instead of embedding the mapping
  table"): `/gate-audit`'s own session, which dispatched the auditors itself in the same
  context, and `workflows/epic-driver.js`'s `auditFanIn()`, which dispatches a fresh agent to
  compile reports it never saw generated.
- **Genericize scope language.** "this command" / "the report below" become "this audit
  round" / "the diff scope established for this round" — phrasing that resolves correctly
  whether the round is `/gate-audit`'s own merge-base-to-`HEAD` computation or `auditFanIn`'s
  `dir`/`base` parameters. The line "you already have Read/Glob/Grep/Bash access to the full
  changeset" becomes reader-neutral: the compiling reader either has that access directly
  (`/gate-audit`'s own session) or was handed the changeset diff/scope explicitly in its
  dispatch prompt (`auditFanIn`'s existing `dir`/`base`/`reports` construction) — either way,
  it has what it needs to confirm a citation; the rule doesn't change, only how it's phrased.
- **Fold in "routed out" as a named third lane state**, alongside carry-forward and AGENT
  DIED — the set the acceptance criteria name together. Today, `gate-audit.md`'s own "After
  all auditors return" section only names two states, because a routed-out auditor (9–12,
  6–8) never reaches compilation in the standalone gate at all: its skip note is already
  stated during "Launch all auditors in parallel," in the same session, before compilation
  starts. `epic-driver.js`'s `auditFanIn()` already defines an explicit third state for its
  dispatched compiler, which never witnessed the routing decision (first-round changeset
  routing, #138) — carried in `joinReports()`'s `routedOutBlocks` and `auditFanIn`'s own
  prose. Naming all three here, once, gives `/gate-audit`'s own compilation step the same
  explicit vocabulary its routing already implies (a Launch-time skip note was always,
  de facto, "routed out"; it just wasn't named that at compile time). This is a vocabulary
  unification, not a judgment change: which auditors ran and what verdict results is
  identical before and after.
- **Keep the severity-tier pointer** (`reference/severity-rubric.md`) verbatim — it already
  delegates; only its location moves.
- **Keep the critical-challenge process** (confirm/downgrade/drop, the code-content vs.
  non-code claim-type split) verbatim in substance, with the scope-language genericization
  above applied.
- **Keep the report-format subsections** (Summary / Critical findings / Important findings /
  Track findings) and the `### Verdict` tier list (`PASS` / `FIX AND RE-AUDIT` / `NEEDS
  DISCUSSION`) verbatim — both callers must produce byte-identical report structure and the
  same three verdict tokens, since `hooks/gate-reminder.sh` and `bin/gate-ledger`'s
  `cmd_status` read a recorded verdict the same way regardless of which path produced it.
  `reference/gate-vocabulary.md` already lists these three tokens as the audit gate's
  canonical spellings; the new file's `### Verdict` section is the substantive definition of
  what drives each one (a compile-time rule), not a second copy of the token list, so it
  isn't the duplication `gate-vocabulary.md` exists to prevent — see Open questions for the
  narrow judgment call this distinction leaves to build.

### 2. `gate-audit.md`'s "After all auditors return" section becomes a pointer

Replace the section with a short paragraph naming `reference/audit-compilation.md`, in the
same voice as `gate-audit.md`'s own existing pointers to `reference/severity-rubric.md` and
`reference/audit-routing-signals.md` ("consult it, don't restate it"). `## Record the
verdict` (lines 161–189) — a sibling `H2` section, not part of "After all auditors return"
— is untouched: its ledger-recording mechanics (the literal `gate-ledger record` invocation,
the `--blocking-lanes` construction rule) already differ per consumer (`gate-audit.md` runs
its own bash command; `auditFanIn`'s prompt carries its own separately-worded `cd "${dir}" &&
gate-ledger record ...` instruction) and aren't named in the acceptance criteria's extraction
list.

### 3. `epic-driver.js`'s `auditFanIn()` points at the new file

Line 527's opening sentence becomes "Read `reference/audit-compilation.md` from the plugin
root and apply its compilation rules to the auditor reports below" in place of "Read
`commands/gate-audit.md` from the plugin root ... and apply ITS compilation rules." Because
`auditFanIn()` backs both `auditRound()` and `finaleAuditRound()`, this one edit covers both
invocation paths — no other function in the file reads `gate-audit.md` for compilation
purposes (grep confirms every other `gate-audit.md` mention in `epic-driver.js` is a code
comment describing dispatch-side mirroring — routing signals, diff precompute — read by a
human maintainer, not by a dispatched agent at runtime). The rest of `auditFanIn`'s prompt —
the pre-mortem out-of-scope carve-out, the routed-out/carried-forward block rendering, the
`blockingLanes` construction rule — is untouched; only the opening pointer changes.

**Explicit boundary.** `gatePrompt()` (the generic per-gate dispatcher, used for
design-review) is never used for the audit gate: `workflows/epic-driver.js:766–770` shows
`gate === 'audit'` always routes to `auditRound()`/`auditFanIn()`. There is no "whole
`gate-audit.md` executed by a dispatched agent" path to worry about breaking — `auditFanIn`
is the only redirect target this story touches.

## User journey

Extends PRODUCT.md's critical user journey #2 ("Per-feature gate flow": `/gate-design-review`
> build > `/gate-audit` [...] > `/gate-acceptance` > merge) to epic scale via
`/work-through`'s per-story and finale audit rounds, the journey's own epic-scale entry
point.

1. The primary persona runs `/work-through` on a multi-story epic. A story finishes its
   build phase; the driver calls `auditRound(story, ...)`, which dispatches the routed
   auditors in parallel, then calls `auditFanIn(...)` to compile their reports into one
   verdict.
2. **Before this story:** `auditFanIn`'s dispatched compiling agent reads the entire 189-line
   `gate-audit.md` to find the ~48 lines of compile rules it applies — 28,049 bytes read to
   use 7,823 of them.
3. **After this story:** the same dispatch reads `reference/audit-compilation.md` directly —
   7,823 bytes, the exact rules it needs, nothing else. The compiled report it produces is
   unchanged in shape and content: same Summary/Critical/Important/Track structure, same
   three lane-state labels (now including "routed out" by name where it was previously
   implicit), same severity mapping, same verdict tokens.
4. This recurs on every `FIX AND RE-AUDIT` retry round for the story (up to
   `MAX_FIX_CYCLES`), and once more at the epic finale via `finaleAuditRound`, compounding the
   savings across the whole epic run.
5. **Must not regress:** a real `PASS`, `FIX AND RE-AUDIT`, or `NEEDS DISCUSSION` verdict on
   a given set of auditor reports is bit-for-bit the same verdict before and after this
   change — this story relocates and unifies wording, it never touches what drives a verdict.
6. The persona sees no difference in `/work-through`'s behavior or output; only the token
   cost of every compile dispatch drops.

## Out of scope

- **Any change to what a compile step decides.** No verdict-token change, no severity-mapping
  change, no new lane state beyond naming "routed out" where it was already implicit. The
  epic's own boundary governs: cost and visibility only.
- **`reference/severity-rubric.md`, `reference/audit-routing-signals.md`,
  `reference/gate-vocabulary.md`'s own content** — cited by the new file, not edited.
- **`gate-audit.md`'s dispatch-mechanics sections** (shared-contract assembly, diff
  precompute, evidence-log resolution, re-audit-scope narrowing, the 13 numbered auditor
  entries, changeset-routing prose). `/gate-audit`'s own interactive session still needs all
  of this to run the audit; none of it moves.
- **`## Record the verdict`** — untouched, per Proposed design §2.
- **The epic's five other findings** (auditor-8's inline dispatch cost, `gate-audit.md`'s own
  routing/dispatch-side cost work already shipped in earlier releases, `work-through`'s
  per-story reconcile round-trips, `handback`'s redundant evidence reads, the unbounded
  evidence log, `gate-acceptance`'s invisible dispatch retries) — separate stories in this
  epic, untouched here.
- **Updating the existing pytest suite that pins text inside the moved section** — named as a
  build-phase task in Operational readiness below, not designed here; this doc identifies the
  affected tests so build doesn't discover them cold.

## Alternatives considered

- **Instruct `auditFanIn`'s compiling agent to read only the "After all auditors return"
  section of `gate-audit.md`, without extracting a new file.** Rejected: there's no
  partial-file read primitive in a dispatch — the agent still opens and pays for the whole
  file to find the section by name, so no byte savings materialize. It also leaves two
  audiences reading one file for different reasons, the exact coupling issue #159 names, and
  makes the compile half fragile to any future edit of the dispatch half's headings — the
  existing `test_gate_audit_challenge_step.py`'s regex-based section extraction already shows
  this fragility today.
- **Leave "After all auditors return" duplicated — a real copy in `gate-audit.md`, a second
  copy inline in `auditFanIn`'s prompt string — kept in sync by hand.** Rejected: this is the
  same "second copy that could drift" pattern `reference/audit-routing-signals.md`'s own
  design (#138) already rejected, and directly violates acceptance criterion 3.
- **Split into two reference files, one per audience** (e.g. a compile-lite file for
  `auditFanIn` without the full report-format subsections, since `/gate-audit`'s own session
  could format its output however it likes). Rejected: both callers must emit the same
  Summary/Critical/Important/Track structure and the same three verdict tokens for
  `hooks/gate-reminder.sh` and `cmd_status` to read a recorded verdict consistently regardless
  of which path produced it. Splitting the format definition itself would reintroduce the
  two-copies risk this story removes.
- **Also relocate `## Record the verdict` into the new file.** Rejected: its content is
  already consumer-specific — `gate-audit.md`'s own literal `gate-ledger record` bash block
  vs. `auditFanIn`'s separately-worded `cd "${dir}" && gate-ledger record ...` instruction —
  there's no single verbatim text to extract without either losing the consumer-specific
  worktree wiring or introducing placeholder templating the acceptance criteria never asked
  for. Also not named in the acceptance criteria's extraction list.

## Success metrics

No user-facing or production-telemetry surface — this is an internal prompt-cost and
documentation-hygiene change; there is no runtime dashboard to read it from. Per the
design-doc contract, the observable signal is structural and directly checkable in the repo:

- **Bytes the compile dispatch is pointed at:** 7,823 bytes / 48 lines
  (`reference/audit-compilation.md`) vs. 28,049 bytes / 189 lines (whole `gate-audit.md`)
  today — a ~72% reduction in reference material `auditFanIn`'s dispatched compiler reads, on
  every story audit round (including retries) and every epic finale round. Verifiable with
  `wc -l`/`wc -c` on both files post-split, and by diffing `auditFanIn`'s opening sentence
  before/after.
- **Zero duplicate copies:** a grep for a distinctive string from the moved section (e.g. "map
  each one's labels into the report's three tiers") resolves to exactly one file,
  `reference/audit-compilation.md` — this is acceptance criterion 3's own static check.
- **`scripts/check_references.py` continues to pass** (acceptance criterion 4) — the
  mechanical proof both pointers resolve to a real file.

## Operational readiness

- **Migration.** Pure content relocation plus two pointer edits — no ledger-schema change, no
  new read at a different point in the flow than today (`auditFanIn` already reads a file at
  compile time; it reads a smaller one now). Three existing pytest files touch the moved
  section or its neighbors and need attention during build:
  - `tests/python/test_gate_audit_challenge_step.py` — all 8 assertions extract a section via
    regex between "consult it, don't restate it." and "Then compile a unified audit report,"
    entirely inside the moved text. This file's target read must become
    `reference/audit-compilation.md`, or every assertion in it fails once `gate-audit.md`'s
    own copy becomes a pointer.
  - `tests/python/test_delta_scoped_reaudit.py` —
    `test_gate_audit_md_and_epic_driver_agree_on_the_ten_lane_roster` reads `gate-audit.md`'s
    `## Resolve re-audit scope` section (a different, untouched section) and is unaffected;
    `test_both_dispatch_surfaces_cite_the_identical_blocking_lanes_flag` checks
    `--blocking-lanes` appears in `gate-audit.md`'s text, which still holds since `## Record
    the verdict` (where that string lives) is untouched. Confirm both still pass; no edit
    expected.
  - `tests/python/test_audit_premortem_scope.py` — asserts specific pre-mortem carve-out
    language inside `auditFanIn`'s own prompt string; unaffected as long as that text is
    preserved verbatim when only the opening pointer sentence changes (the design above keeps
    it verbatim).
  - Build must re-run `uv run --no-project --with pytest pytest tests/python -v` after the
    split and confirm the full suite — not just the newly-affected file — stays green. The
    acceptance criteria name `check_references.py` explicitly; keeping the existing test
    suite's coverage intact is this repo's own standing bar (CLAUDE.md: "bug fixes require
    regression tests" — by extension, a relocation must not silently drop existing coverage
    of the relocated content).
- **Rollback.** Revert the `reference/audit-compilation.md` addition and both pointer edits
  (`gate-audit.md`'s "After all auditors return" section, `epic-driver.js` line 527's opening
  sentence). No data migration, no ledger state affected — `GATE_RESULT`'s shape
  (including `blockingLanes`) is untouched.
- **Rollout.** Ships via the plugin's normal semantic-release cadence; the next `/gate-audit`
  run and the next `/work-through` epic benefit automatically, no user action needed.
- **How we'll know it's working or failing.** `scripts/check_references.py` passing confirms
  both pointers resolve; the static duplicate-copy check confirms exactly one copy exists; a
  manual read of a compiled audit report (standalone or via a `/work-through` story) after the
  change should show byte-identical Summary/Critical/Important/Track structure and identical
  verdict tokens to before — same judgment, smaller doc behind it.

## Open questions

- **Exact placement of the "routed out" fold-in** inside `reference/audit-compilation.md`'s
  lane-state description — a third bullet alongside carry-forward/AGENT-DIED (this doc's
  working assumption) versus its own subsection. Left to build; either satisfies "contains...
  carry-forward/routed-out/AGENT-DIED lane-state rules" as long as all three carry the same
  distinguishing rigor `auditFanIn`'s existing prompt already applies.
- **Whether the new file's `### Verdict` list should state the tiers' meaning in full** (this
  doc's assumption, matching what "After all auditors return" states today) versus deferring
  to `reference/gate-vocabulary.md`'s token table and adding only a cross-reference.
  Recommendation: keep the substantive definition here (what drives a `PASS` vs. `FIX AND
  RE-AUDIT`) and treat `gate-vocabulary.md` as the token-spelling source only — that file's own
  stated purpose is "one spelling," not the compile-time rule for reaching one. Not a blocking
  question; build should follow the recommendation unless a design-review round flags it.
- **Whether `reference/gate-vocabulary.md`'s `audit` row should also note
  `reference/audit-compilation.md`** as a second citation alongside `commands/gate-audit.md`.
  Not required by any acceptance criterion; flagged for the maintainer's judgment, not decided
  here.
