# Post-merge platform re-evaluation — 2026-07-25

One-off strategy review, run three days after jig was absorbed (#150, PR #171, v2.26.0).
Filed at `docs/` root alongside `initiative-altitude.md` and `jig-issue-transfer-map.md` —
these are repo-level decision records, not `/deep-review` output. It is deliberately **not**
in `docs/studious/*-reviews/`, which holds periodic-review trend history (see finding T2 for
why that directory is currently confounded).

**Method.** Inline reading of the whole prompt/script surface at `a2be1b2`, plus the 69 open
issues and 13 milestones via `gh`. No subagents, no `/deep-review`, no workflows — per the
session constraint. Every finding below carries a `file:line` or a reproducible command. Two
findings are proven by executing the repo's own tooling.

**Status.** All three phases have since been executed on the tracker — see the two execution
records at the end of this document. Phases 1 and 3 were written as proposals and are preserved
as written; where execution diverged from the proposal, the Phase 3 record says so. The `gh`
commands listed in Phase 3 are what was actually run, in a script with integrity assertions.

---

## Summary

The merge unified the **repo**. It did not unify the **flow**.

One diff domain, one version line, one install — all delivered, and the load-bearing
guarantee (`scripts/check_gate_independence.py`) is real and enforced. But at the flow layer
the platform still carries two of nearly everything, one from each side of the old boundary:
two navigators with two state stores, two evidence grammars, two closeouts, two design-doc
authorities, two doc homes, two conventions for what a skill is.

Most of that is cosmetic drift that will cost a contributor an hour. Two items are not:

- **The design seam is self-contradictory, and the linter enforces the wrong side of it.**
  `scripts/design-lint` rejects the plugin's own shipped `templates/design-doc.md` — 8
  sections against a contract the linter says requires 7, while that contract requires 8.
  Provable in one command, and it means a hand-authored doc following the scaffold both
  navigators point at cannot pass `/plan`'s lint. (C1)
- **The gate-independence rule caught a dispatcher, not a gate.** `workflows/epic-driver.js`
  is on the protected surface, so `/work-through` — the flagship autonomous path — is barred
  from naming the in-box build loop and tells its workers to use Superpowers instead. (C2)

The backlog has the same shape: 13 milestones, 5 of them named by *which repo the work came
from*, which is precisely the distinction #150 existed to erase. 20 of 69 open issues carry
no milestone at all — the largest single bucket.

Phase 3 proposes 8 milestones split by *what the work serves*, with the flow-coherence work
first because the other six ride on it.

**Executed 2026-07-25.** Phase 2 and Phase 3 were both carried out on the tracker the same day:
7 issues closed, 5 rewritten, 18 filed, all 80 open issues re-milestoned, 13 milestones reduced
to 8 with none named by origin and none left unassigned. The Phase 1 findings above describe the
codebase at `a2be1b2` and still stand; the *tracker* state they describe is pre-restructure, so
a future cycle trending against this baseline should read the execution records at the end for
the post-restructure numbers.

---

## Phase 1 — Codebase and workflow state

### The theme

Both halves of the platform are internally coherent. The seam between them is where every
finding lives. Concretely, these pairs never got reconciled:

| Concern | Gate side | Build side | Reconciled? |
|---|---|---|---|
| "What's next?" | `/work-on` (6 pieces, `.studious/work/*.json`) | `/coach` (7 steps, `PLAN.md` suffixes) | No — neither reads the other's store |
| Design-doc authority | `reference/design-doc-contract.md` (8 sections) | `scripts/design-lint` (7 sections) | No — actively contradictory |
| Evidence | `.studious/evidence/*.jsonl` → `/handback` | `docs/jig/evidence/<date>-<task>/` → `/finish` | No — and CI blesses the thinner one |
| Closeout | `/work-on` done → "PR is yours" | `/finish` → `MERGE\|PR\|KEEP\|DISCARD` | No — plus `/handback` as a third |
| Design records | `docs/superpowers/{plans,specs}/` | `docs/design/` (gitignored) | No |
| What a skill is | trigger shim → command | the implementation, no command | No — CONTRIBUTING/DESIGN.md say shim |

Severity uses this repo's own ladder (`reference/severity-rubric.md`), read as: **Critical** —
producing wrong behavior now, fix before more work rides on it; **Important** — fix this
cycle; **Track** — log and revisit.

### Critical

**C1 · The design-doc contract, the linter, the template, and `/design` disagree — and both
directions are enforced by code.**

`reference/design-doc-contract.md` lists **8** required sections (rows at `:11–:18`),
including `Success metrics`, added when #120 closed on 2026-07-18.
`templates/design-doc.md` ships **8** matching `##` headings. But:

- `scripts/design-lint:82–90` — `CANONICAL_SECTIONS` holds **7**. No `Success metrics`.
- `scripts/design-lint:273–277` — hard-fails when the count isn't exactly 7.
- `skills/design/SKILL.md:141–163` — instructs `/design` to write those same 7, claiming they
  are "`design-doc-contract.md`'s seven section names — the contract-canonical convention."
- `DESIGN.md:112` — "exactly 7 sections," listing the same 7.

Proof, run against the plugin's own shipped scaffold:

```
$ uv run --no-project python scripts/design-lint --doc templates/design-doc.md --repo .
[FAIL] section count and vocabulary: section 'Success metrics' does not match
       design-doc-contract.md's seven required section names
[FAIL] section count and vocabulary: 8 top-level sections found;
       design-doc-contract.md requires exactly 7
```

The linter cites `design-doc-contract.md` as its authority for "seven" while that file lists
eight. Two live consequences:

1. **A hand-authored doc following the shipped template fails `design-lint`.** Proven above.
   That template is what `/work-on:78` and `/gate-design-review:14` both point users at, and
   it is the doc a `/work-on` user hands to `/plan`.
2. **`/design` output has no home for Q7.** `skills/design/SKILL.md:143–163` assigns every
   section a named consumer — Q1, Q2/Q6, Q3, Q4, Q5, the operability lane, the human sponsor.
   **None is Q7.** `/design` also omits the section the contract created for it, and would
   fail its own linter if it wrote one. Whether that becomes a gate finding is **unverified
   and depends on prose**: `agents/product-reviewer.md:34` keys check 7 on substance, not on a
   heading — "Does the doc say how we will know the feature worked… a missing or empty answer
   is a finding, not a pass" — so a reviewer may answer Q7 from text that happens to land in
   `Proposed design` or `Operational readiness`. Nothing in the pipeline makes that happen on
   purpose, and `design-doc-contract.md:5` maps a missing answer to **REVISE**. Treat this as
   a designed-in gap, not a demonstrated failure — the demonstrated failure is (1).

Neither surface is wrong on its own. #120 landed on the contract and the template and never
reached the linter or `/design` — a pre-merge seam that the merge made load-bearing.
**NEW.** Adjacent to #210 and #203 but distinct from both: #210 asks what the review model
*should* be; this is that today's is self-contradictory.

**C2 · `/work-through` is structurally barred from naming the in-box build loop, so it names
Superpowers.**

`scripts/check_gate_independence.py:36–41` puts `workflows/*.js` on the protected gate
surface (`:39`); `:49` forbids any `/design|/plan|/build|/finish|/coach` invocation there. The rule is
right — a gate must judge work, never its producer. But `epic-driver.js` is a **dispatcher**,
not a gate, and it got caught. The consequence is at `epic-driver.js:786`:

> "You MAY use the **Superpowers plan/execute workflow if installed**; the worker contract is
> normative either way."

That is the only executor named in the epic path. Meanwhile `/work-on` — the story-scale
navigator, not on the protected surface — names `/plan` + `/build` freely (`work-on.md:79`,
`:101`), as does `README.md:73`. So the platform's most autonomous entrypoint routes work to a
third-party tool it merely interoperates with, while the supervised entrypoint routes to the
loop that ships in the box.

The fix is a scope question, not a rule reversal: the driver *dispatches* against
`reference/worker-contract.md` and never *judges*, so it plausibly belongs outside
GATE_SURFACE — but `epic-driver.js` also contains the gate compile prompts (`auditFanIn`,
`acceptanceFanIn`), so a blanket exclusion is wrong too. Needs a deliberate decision, not a
regex tweak. **NEW.**

Second-order, same line: `epic-driver.js:786` writes `--outcome DONE`, while
`skills/build/SKILL.md:577` writes `BUILT|PAUSED|ESCALATED` and
`reference/worker-contract.md`'s "Status reporting" section names the same three.
`work-on.md:54` handles only those three and has no case for `DONE`.
`bin/gate-ledger:436–447` validates no enum on `--outcome`. Three writers, two vocabularies,
one unvalidated slot.

Reachable, not theoretical. Epic work slugs are namespaced (`workSlug()` at
`epic-driver.js:634` → `<epic>--<story>`, per #104), so the two stores don't collide by slug —
but `epic-driver.js:779` records `work-set --slug … --branch "<storyBranch>"`, and
`work-on.md:38` resolves by **branch**: "If a work file's branch matches the current branch,
that's the feature." A user who runs `/work-on` while checked out on an epic story branch
matches that row, reads its most recent `step: "build"` entry, and finds `DONE`.

### Important

**I1 · Two navigators answer "what's next" from two state stores that don't read each other.**

| | `/work-on` (`commands/work-on.md`) | `/coach` (`skills/coach/SKILL.md`) |
|---|---|---|
| State read | `work-get`/`work-list`, `gate-get` | `PLAN.md` suffixes, `git log`, `docs/design/*`, `docs/jig/evidence/`, `gate-get`, `status` |
| State written | `work-set`, `work-log` | none (read-only by design) |
| Flow modeled | 6 pieces; no plan step, no finish step | design → design-review → plan → build → audit → acceptance → finish |
| Ends at | "the PR is theirs to open" (`:26`, `:142`) | `/finish` (`:96`, `:115`) |
| Knows about | `/design`, `/plan`, `/build` | four gates + four build skills |
| Never mentions | `/coach`, `/finish` | `/work-on`, `/work-through`, `/handback` |

One direction is wired: `skills/build/SKILL.md:576–580` writes `work-log --step build`, so
`/work-on` sees `/build`'s terminal status. Nothing closes the loop — `/coach`'s signal table
(`:47–:53`) never calls `work-get`, so a feature actively tracked in a `/work-on` work file is
invisible to the coach, which will re-derive position from `PLAN.md` and recommend a step
`/work-on` already logged.

A user with both entrypoints in one plugin gets two different answers to the same question.
**NEW.**

**I2 · Three closeouts, two evidence stores, and CI blesses the thinner one.**

- `.studious/evidence/<branch-slug>.jsonl` — one JSONL record per verification *command*,
  written by `hooks/evidence-capture.sh:4`, gitignored, grammar pinned in
  `reference/evidence-format.md`, consumed by `/handback` → commits
  `docs/studious/handback/<branch-slug>.md`.
- `docs/jig/evidence/<date>-<task>/` — verification *artifacts* plus a freshness-stamped
  manifest, written by `scripts/evidence-capture:5`, committed, consumed by `/finish` → PR
  evidence table + dated build report.
- `/work-on` piece 6 produces neither and ends with "the PR is theirs to open."

`scripts/check_gate_independence.py:53` names `docs/jig/evidence` a forbidden build artifact
for gates and points them at `reference/evidence-format.md` instead. So the richer,
committed, freshness-verified store is the one no gate may read, and the thinner ephemeral one
is the sanctioned contract. That is defensible (any executor can satisfy the JSONL grammar;
only `/build` produces the folders) but it is not written down anywhere as a decision, and it
means `/finish`'s PR evidence table and a gate's evidence citation describe the same branch
from two disjoint sources.

Maps to **#148**, whose premise has shifted: it was filed as "one receipt grammar across the
portfolio" — a cross-repo negotiation. It is now "one repo, two formats, and a CI rule that
picks the thinner one." Substance survives; framing is stale. Related: **#145** (dossier),
**#179** (folder collision bug).

**I3 · `/studious-doctor`'s tooling check never grew a build-side row.**

`commands/studious-doctor.md:14–16` checks exactly three things: git repo, `jq`, `gh auth`.
All three are gate-side dependencies. Not checked:

- `python3` — every `scripts/*` CLI that `/plan`, `/build`, and `/finish` shell out to.
- `viva` — declared in `.claude-plugin/plugin.json` as the only `dependencies` entry, and
  CLAUDE.md is explicit: "`/plan` and `/design` stop dead without it."

The command exists specifically to surface silent degradation, and half the product is now
outside its check. Its roster check (§2) did scale correctly — it globs `skills/*/SKILL.md`,
so the five new skills are covered there. Only §1 is stale. **NEW.**

**I4 · The design doc is disposable; everything named after it is durable.**

`/design` writes `docs/design/<slug>.md` (`skills/design/SKILL.md:138`). `.gitignore:17`
ignores that directory, with the rule stated at `:12–:15`: design docs "die at merge."
Meanwhile:

- `gate-design-review.md:11` discovers the doc via
  `git diff --name-only $(git merge-base HEAD origin/main)...HEAD`. A gitignored file never
  appears there. The filesystem fallback at `:12` ("most recently modified Markdown") does
  rescue it — so this degrades rather than breaks — but the in-box producer's output is
  always found by the fallback, and the fallback picks by mtime, which is wrong on any branch
  carrying two docs.
- `gate-design-review.md:55` names the pre-mortem register
  `docs/studious/premortems/<doc-slug>.md` — **committed** — after the filename of a doc that
  is deleted at merge (`skills/finish/SKILL.md:224`).
- `work-on.md:52` re-derives the register path from the recorded `designDoc`, and warns
  against using the feature slug instead.

Post-merge, a committed register on `main` points at a filename that no longer exists, and the
navigator's path derivation for it stops working. **NEW.** Overlaps #181 (this repo force-adds
its own `docs/design/`, which is why the breakage isn't visible here) and #210.

**I5 · Stale two-repo framing survives inside shipped prompts, past the guard built to catch
it.**

`tests/python/test_no_jig_prose.py` guards the literal word "jig" across shipped surfaces and
passes. It does not catch the framing, which is the part a reader actually acts on:

- `skills/build/SKILL.md:391` — "no dependency on studious being installed at all"
- `skills/build/SKILL.md:581` — "see `reference/worker-contract.md`'s ... in the studious repo"
- `skills/build/SKILL.md:612` — "never a new dependency on `gate-ledger` or on studious being
  installed at all"
- `skills/finish/SKILL.md:9`, `:15` — "studious's `/gate-audit` and `/gate-acceptance` (if
  installed)"
- `.github/workflows/ci.yml:30` — job name "Gates never require jig"

Studious *is* the plugin; the gates always ship. A reader following `skills/build/SKILL.md:391`
believes a conditional exists that does not.

(`skills/finish/SKILL.md:106`'s "sibling plugin" is about **cctx**, a genuinely separate tool
— correct as written, not a finding.)

Same drift class as **#209**, which covers bare `#N` issue references only. The instances above
are new, and the guard should be extended rather than the prose swept once.

**I6 · The shim convention no longer describes half the skills directory, and the README calls
skills commands.**

- `CONTRIBUTING.md:43` and `DESIGN.md:130–132` both define a skill as a trigger shim whose
  "body delegates to the matching command rather than duplicating it."
- 5 of 13 skills are the implementation with no command behind them.
  `skills/build/SKILL.md` is 616 lines — the largest prompt file in the repo.
- `README.md:162` — "Every command Studious ships" — then lists `/design`, `/plan`, `/build`,
  `/finish`, `/coach` at `:176–:180`. They are skills.
- `DESIGN.md:125` still describes command naming as "verb-prefixed families"; the five build
  entrypoints are bare verbs.

CLAUDE.md already concedes the change ("`/design`, `/plan`, `/build`, `/finish`, and `/coach`
are `skills/` here like any other"). The two documents contributors are actually pointed at
do not. **NEW.**

### Track

**T1 · Three homes for the same concept.** `docs/superpowers/{plans,specs}/` holds *this
repo's own* design records, named after a third-party product it merely interoperates with;
`docs/design/` holds jig-lineage docs (gitignored, force-added here); `docs/jig/` holds a
pre-merge changelog and the evidence tree. A contributor writing a design doc for this repo has
no rule to follow. **NEW.**

**T2 · The committed review history under `docs/studious/` is jig's, unlabelled.** All three
2026-07-17 reports arrived in `980d523` (the merge commit). Each declares itself a baseline for
"this project," and `health-reviews/2026-07-17-deep-review-summary.md:5` names the reviewed
tree as `/Users/bryan/Projects/jig`. The next `/deep-review` on studious will trend its metrics
against a different product's baseline, and `review-codebase-health`'s metrics-snapshot keys
(#115) are exactly the join keys that would silently fork. **NEW.**

**T3 · The shipped-executable boundary is split across `bin/` and `scripts/` with no rule.**
`bin/` holds `gate-ledger` + `board-server`; `scripts/` holds 4 CI helpers alongside 8 shipped
runtime CLIs. Same lifecycle question, two directories — and
`check_gate_independence.py:41` has to enumerate `bin/gate-ledger` by name in order to exclude
`bin/board-server`, which is the tell. **NEW.**

**T4 · `PLAN.md` is tracked at the repo root despite `.gitignore:16`.** Already **#181**.

**T5 · PRODUCT.md carries extraction scaffolding as authoritative text.** Four `<!-- FILL IN
-->` TODOs, a "Confidence summary" section, and a "Current known problems" list whose top item
(#24, "the quality tool has no quality gate on itself") is closed — CI now runs 7 jobs. Its
"Feature tracker" section still describes the A/M/X tiers, superseded by M1–M9. Already
**#147**, whose title says it precisely: "gates are reading stale ground truth." The merge
widened it — PRODUCT.md now also has to describe a build loop.

### Finding → issue map

| # | Finding | Disposition |
|---|---|---|
| C1 | `design-lint` rejects the shipped template; contract/template/`/design`/DESIGN.md disagree on the section set | **NEW** |
| C2 | epic-driver barred from naming in-box executor; `DONE` vs `BUILT` vocabulary | **NEW** |
| I1 | two navigators, two state stores, no mutual read | **NEW** |
| I2 | two evidence stores, three closeouts; CI blesses the thinner | #148 (rewrite), #145, #179 |
| I3 | `/studious-doctor` has no build-side tooling row | **NEW** |
| I4 | disposable design doc, durable register named after it | **NEW** (overlaps #181, #210) |
| I5 | stale two-repo framing past the no-jig-prose guard | #209 (extend) |
| I6 | shim convention + README call skills commands | **NEW** |
| T1 | three doc homes | **NEW** |
| T2 | jig's review reports in studious's trend directories | **NEW** |
| T3 | `bin/` vs `scripts/` boundary has no rule | **NEW** |
| T4 | tracked root `PLAN.md` | #181 |
| T5 | PRODUCT.md stale + extraction scaffolding | #147 |

Eight NEW, five already tracked.

### What is working

Worth stating, because the findings above are all seam-shaped and could read as a verdict on
the merge itself. It is not.

- **The load-bearing rule holds.** `check_gate_independence.py` is a real check on a real
  surface (matched-file floor at `:78` prevents a vacuous pass), and it caught the one thing
  most likely to erode. C2 is a scoping bug *in* that check, not evidence against it.
- **The roster mechanisms scaled without edits.** `/studious-doctor`'s §2 glob,
  `test_no_jig_prose.py`'s SHIPPED tuple, and `deep-review`'s prompt-surface detection all
  absorbed five new skills with no change.
- **CI grew correctly.** 7 jobs, two deliberately separate test runners, ruff pinned,
  shellcheck and eslint on the executable surface.
- **One version line, one install, one manifest** — the merge's stated goal, delivered.

---

## Phase 2 — Backlog review

69 open issues, 13 milestones. Three problems: redundancy the merge created, premises the
merge invalidated, and coverage gaps.

### 2.1 Resolved but still open

**#163 — "epic-driver.js never dispatches premortem-auditor at story-level acceptance."**
Fixed. `workflows/epic-driver.js` now carries `acceptancePremortemDispatchPrompt` (`:283–285`)
dispatching inside `acceptanceRound`'s parallel batch, the fallback branch-header discovery
(`:290–315`), and the third compile block in `acceptanceFanIn` (`:318–335`). That is exactly
Tasks 1–4 of the root `PLAN.md` ("acceptance-dispatch-fix"), all `[PASS]`, merged as `c31ace3`
(PR #168). Issue last updated 2026-07-22, one day before the fix's design spec.
→ **Close, citing `c31ace3`.**

### 2.2 Redundant — the merge collapsed the distinction

The `jig: Telemetry & replay` milestone description says it outright: *"Overlaps studious
#132–#135; dedupe once transferred."* That work is still pending. Two dispositions, kept
distinct because they lead to different actions:

**Premise invalidated → close.**

| Issue | Why |
|---|---|
| **#185** "Open question: per-stage model routing" | #187 says of itself: *"This is the concrete contract #185 gestures at."* #185 adds nothing #187 + #189 don't carry. Close as superseded. |
| **#163** | Shipped (§2.1). |

**Substance survives, framing is stale → rewrite, don't close.**

| Issue | What's stale | What survives |
|---|---|---|
| **#187** "Shared routing-table contract (schema + routing_reason vocabulary, **read by jig and studious**)" | The entire "Placement note: no obvious home repo… co-located by pragmatic choice" rationale. There is one repo. | The schema and the `routing_reason` vocabulary. Retitle to drop "read by jig and studious." |
| **#188** "Replay harness" | Same placement note — half-stale. jig and studious merged; cctx and docent are still separate, so the ownership question is narrower, not gone. | The harness and the oracle hierarchy. |
| **#189** "Dynamic model classifier (evidence-gated on **#40/#41**)" | `#40`/`#41` are jig-era numbers that now resolve to unrelated studious issues — an *active misreference*, not cosmetic. Correct target is #187 + the replay data. | The idea and its build gate. |
| **#190** "Run the speed/price-per-task audit on **jig's** dispatch surfaces" | Filed as "the audit that was run on studious but not on jig." One codebase now — one audit, spanning both dispatch surfaces. | The backward-looking audit itself, which #130 and #144 genuinely don't cover. Merge into #130's scope or retitle to "the build-side dispatch surfaces." |
| **#148** "Shared evidence-format contract **with jig** — one receipt grammar across the portfolio" | The cross-repo negotiation framing. | Finding I2's substance, sharpened: one repo, two formats, and a CI rule that blesses the thinner one. Retitle and re-scope against I2. |
| **#132** vs **#186** | Not duplicates — different dispatch surfaces (gate auditors vs build tasks), and #132 already says "do not build a parallel telemetry path." What's wrong is that they sit in *different milestones split by origin*, which guarantees two schemas get designed. | Both. Same milestone, #186's event shape as the shared schema. |

**Structurally redundant → consolidate.**

Five issues of identical shape: **#175, #177, #178, #180** ("m1 / m1-followup / m4-build-core
/ m4-closeout audit Track-tier findings, bundled, revisit next cycle") and **#207**
("deep-review-2026-07-17 Track-tier findings, bundled"). Each is a bag of deferred Track
findings from one gate run. Five bags is not a backlog — it's a deferred-triage queue wearing
issue numbers, and nothing will ever pick one up as a unit of work.
→ **Triage each bag once: promote the findings that still matter into real issues, close the
bags.** If the pattern is worth keeping, keep exactly one rolling issue.

Related shape: **#124** and **#118** are both "periodic X-health lane — deferred pending
gate-lane evidence," with explicit entry conditions and "not actionable until." Correct to
keep; wrong to hold in an *active* milestone (M3) — see Phase 3.

### 2.3 Missing — proposed new issues

Phase 1's eight NEW findings, ordered by the sequencing in Phase 3. Titles written to the
repo's conventions (action-first, specific noun):

| Proposed title | From | Tier |
|---|---|---|
| `design-lint` enforces 7 sections against a contract requiring 8, and rejects the plugin's own `templates/design-doc.md` | C1 | Critical |
| `epic-driver.js` is on the gate surface, so `/work-through` names Superpowers instead of the in-box build loop | C2 | Critical |
| Build-step outcome is an unvalidated free string: `epic-driver` writes `DONE`, `/build` writes `BUILT\|PAUSED\|ESCALATED` | C2 | Important |
| `/work-on` and `/coach` answer "what's next" from two state stores neither reads | I1 | Important |
| `/studious-doctor`'s tooling check covers git/jq/gh only — no `python3`, no `viva` | I3 | Important |
| A `/design` doc dies at merge; the pre-mortem register named after it does not | I4 | Important |
| CONTRIBUTING and DESIGN.md still define skills as trigger shims; 5 of 13 are the implementation | I6 | Important |
| Extend `test_no_jig_prose` to catch two-repo *framing*, not just the word "jig" | I5 | Track |
| Pick one home for this repo's own design records (`docs/superpowers/` vs `docs/design/`) | T1 | Track |
| Label or relocate jig's 2026-07-17 reviews so studious's trend history starts clean | T2 | Track |
| State the `bin/` vs `scripts/` rule for shipped executables | T3 | Track |

Also missing, and not derivable from Phase 1: **#149 remains the only outward-facing issue in
69.** Its own body called this out pre-merge ("both backlogs carry zero outward-facing issues
— everything is hardening, telemetry, cost"). The merge doubled the backlog and did not change
that ratio. Worth stating plainly as a portfolio-level observation rather than a new issue.

---

## Phase 3 — Re-roadmapping proposal

### The problem with the current structure

13 milestones. **Five are named by which repo the work came from** — `jig: Context-doc truth`,
`jig: Hardening & bug tail`, `jig: CI & release guards`, `jig: Telemetry & replay`,
`jig: Open questions` — plus `M7 — The jig seam`, named for a boundary that no longer exists.
That is the exact distinction #150 was filed to erase, preserved in the planning layer.

It has a cost beyond tidiness: #132 and #186 are two halves of one telemetry schema sitting in
two milestones, which is how you end up designing the event shape twice.

Three further problems:

- **20 of 69 issues carry no milestone** — the largest bucket, and it contains real bugs
  (#208, #206, #202, #203, #204) alongside the two Critical findings above.
- **Three milestones hold nothing actionable.** M3 (#124, #118 — both "not actionable until"),
  M4 (#96 — entry-gated), `jig: Open questions` (6 deferred questions). Parked work in active
  milestones makes the roadmap read as busier than it is.
- **M5 mixes horizons.** Near-term telemetry plumbing (#132–#135) sits with Horizon-3
  moonshots (#31, #33, #34-parked) under one heading.

### Proposed milestone set

One axis: **the flow the work serves.** Eight open milestones, none named by origin.
`M10`/`M11`/`M12` are proposed labels — they don't exist in the repo yet; M5/M6/M8/M9 are the
existing ones, kept or renamed.

| Milestone | Holds | Issues |
|---|---|---|
| **M10 — Post-merge flow coherence** *(new, first)* | Make the merge real at the flow layer. Phase 1's Critical + Important findings and the seam issues already filed. | 2 new Critical + 5 new Important, #210, #148 (rewritten), #174, #147, #173, #204, #203, #202, #198 |
| **M11 — Correctness & bug tail** *(new)* | Real defects, wherever they came from. | #208, #181, #179, #206, #205, #200, #201, #165, #166, #197, #170, #169, + the triage of #175/#177/#178/#180/#207 |
| **M6 — Gate & build cost** *(rename)* | Cost is the UX, both pipelines. | #130 (absorbing #190), #144, #136, #157, #199 |
| **M9 — Contract & drift guards** *(rename)* | Stop the drift Phase 1 found from recurring. | #115, #116, #125, #164, #176, #209 (extended per I5), #182, #183, #184 |
| **M12 — Telemetry & outcome labels** *(new)* | One dispatch-telemetry schema across both surfaces, plus the labels that make it joinable. | #186 + #132 (one schema), #133, #134, #135, #187 (rewritten), #186's cctx dependency |
| **M8 — Receipts & front door** *(keep)* | Make the discipline legible. | #145, #149, #129 |
| **M5 — Post-ship outcome loop (X-series)** *(narrow)* | Horizon-3 only. | #65, #31, #32, #33, #146, #188 |
| **Parked — evidence-gated** *(new)* | Everything with a stated entry condition and no date. Not a backlog; a register. | #96, #118, #124, #189, #191–#196, #34 |

**Close:** M7 (seam is internal), and all five `jig:` milestones once emptied.
**Delete-by-absorption:** M3 and M4 (their contents move to Parked).

Net: 13 → 8 open milestones; 20 unmilestoned issues → 0; 49 currently-milestoned issues re-slotted.

### Sequencing, and why

1. **M10 first.** C1 is producing wrong gate verdicts today, and C2 misroutes the flagship
   autonomous path. Everything else — telemetry keys, dossiers, cost budgets — assumes one
   flow exists to instrument. Building on two flows means building twice.
2. **M11 in parallel.** Independent, cheap, mostly mechanical; no dependency on M10's
   decisions.
3. **M9 immediately after M10.** Its whole job is preventing M10's fixes from re-drifting. #115
   (metrics-key contract test) and the extended #209 guard are the pattern; C1 is the argument
   for them — a four-surface contradiction that shipped because nothing pinned the surfaces
   together.
4. **M6 after M10.** #130's re-audit-width question changes shape once the flow is one flow,
   and #190's build-side audit only merges cleanly into #130 post-M10.
5. **M12 after M9.** Telemetry keys are a cross-surface contract; ship the guard pattern first
   or #115's failure mode repeats with more keys.
6. **M8 after M10 + M12.** A per-feature dossier (#145) can only render one flow, and needs
   M12's labels to show outcomes.
7. **M5 last.** Genuinely Horizon-3. #34 stays parked.

The Parked register has no position — it is read at gate time, not scheduled.

### Commands (not run)

Review before executing. Milestone creation first, then moves.

```bash
R=jacquardlabs/studious

# 1. Close the one shipped issue
ghj issue close 163 --repo $R \
  --comment "Fixed by c31ace3 (PR #168): acceptancePremortemDispatchPrompt dispatches at story-level acceptance inside acceptanceRound's parallel batch, with branch-header fallback discovery and a third compile block in acceptanceFanIn."

# 2. Close the superseded one
ghj issue close 185 --repo $R \
  --comment "Superseded by #187, which states: 'This is the concrete contract #185 gestures at.' Routing gate lives in #189."

# 3. Create the new milestones (repeat per row of the table above)
ghj api repos/$R/milestones -f title='M10 — Post-merge flow coherence' \
  -f description='Make the merge real at the flow layer: one design-doc authority, one navigator story, one evidence grammar, one closeout. Blocks M6/M8/M12 — they all assume one flow to instrument.'

# 4. Close the origin-named milestones once emptied
#    (gh has no milestone-close verb; use the API with the milestone number)
ghj api -X PATCH repos/$R/milestones/<N> -f state=closed
```

I have not written the `--milestone` moves as a script — the reassignments should be reviewed
per-issue, and `/backlog-hygiene` is the tool that already exists for that pass.

### Two decisions this proposal needed — both ratified 2026-07-25

**Resolved.** The full decision of record for each is a comment on its issue; the summary:

- **C1 → (a) + (c).** The contract keeps all 8 sections and stays the single authority; `design-lint`, `skills/design/SKILL.md`, and `DESIGN.md` move to 8. Separately, the exact-count check is replaced by "all required sections present, exactly once each" — no upper bound, no rejection of an extra heading — which is what `reference/design-doc-contract.md:20` already specifies and what `product-reviewer` already does. Pinned by a cross-surface test. Recorded on #211.
- **C2 → sub-file granularity.** `workflows/*.js` stays on `GATE_SURFACE`; `check_gate_independence.py` gains an explicitly marked, greppable worker-dispatch region exempt from the `INVOCATION` rule but never from `ARTIFACTS`, with marker-integrity assertions beside the existing matched-file floor. `auditFanIn` and `acceptanceFanIn` stay covered. Recorded on #212.

#### The options as originally posed — superseded by the block above

Kept for the reasoning behind each option, not as an open question. Both were judgment calls where
either answer was defensible, and both gated M10's first issue:

1. **C1's direction.** Three options, not two. (a) `/design` grows a `Success metrics`
   section and `design-lint` moves to 8 — contract wins. (b) The contract drops it, #120 gets
   reverted — linter wins. (c) `design-lint` stops enforcing an exact count and checks
   substance instead, which is what `design-doc-contract.md:20` already specifies ("Sections
   may carry any heading text as long as the content answers the mapped question — the gate
   reads for substance, not exact titles") and what `product-reviewer` already does.
   **I'd take (a) plus (c):** (a) because the contract requiring Q7 is the newer decision and
   the one the gate enforces, (c) because the exact-count check is the thing that made a
   four-surface contradiction possible and it contradicts the contract it cites.
2. **C2's scope.** Does `workflows/epic-driver.js` come off GATE_SURFACE (it dispatches, it
   doesn't judge), or does the surface get file-section granularity (it *does* hold the gate
   compile prompts)? The first is simpler and slightly weakens the guarantee; the second keeps
   the guarantee and adds machinery to `check_gate_independence.py`.

---

## Appendix — reproduction

```bash
# C1
uv run --no-project python scripts/design-lint --doc templates/design-doc.md --repo .

# C2
grep -n "Superpowers" workflows/epic-driver.js
sed -n '36,50p' scripts/check_gate_independence.py

# I1
grep -n "work-get\|work-list" skills/coach/SKILL.md   # no matches

# I5
uv run --no-project --with pytest pytest tests/python/test_no_jig_prose.py   # passes
grep -n "studious repo\|studious being installed" skills/build/SKILL.md

# T2
git log --oneline --diff-filter=A -- docs/studious/architecture-reviews/
```

---

## Execution record — Phase 2 (2026-07-25)

Phase 2 was executed on the tracker the same day. Phase 3 remains a proposal; no milestone was
created, renamed, closed, or reassigned.

### Closed (7)

| Issue | Reason |
|---|---|
| #163 | Shipped by `c31ace3` (PR #168) — story-level premortem dispatch, fallback discovery, third compile block |
| #185 | Superseded by #187, which says so in its own body |
| #175, #177, #178, #180, #207 | Bundled Track-findings bags, triaged and dissolved (below) |

### Rewritten in place (5)

Retitled where the title carried the stale premise, with a dated correction block prepended and
the original body preserved below it: **#148** (evidence grammar), **#187** (routing-table
contract), **#188** (replay harness — placement note half-stale), **#189** (`#40`/`#41` were
jig-era numbers; corrected to #187/#188 per `docs/jig-issue-transfer-map.md`), **#190**
(build-side dispatch audit).

### Filed from Phase 1 (11)

#211 (C1, `design-lint` vs the contract) · #212 (C2, epic-driver on the gate surface) · #213
(build-step outcome vocabulary) · #214 (two navigators) · #215 (`/studious-doctor` tooling
rows) · #216 (design-doc lifecycle) · #217 (skills-as-shims convention, M9) · #218
(`test_no_jig_prose` framing guard, M9) · #219 (design-record home) · #220 (jig's reviews in
studious's trend directories) · #221 (`bin/` vs `scripts/` rule).

### The five bags — triage result

All ~40 checkboxes re-verified against `a2be1b2`, not carried forward on faith.

- **9 had shipped** and were dropped with the evidence stated: the `test_discipline_skill.py`
  dead assignment, `/finish`'s milestone hedge, the non-parallel Pillar headings, the
  "`plan-lint`/`design-lint` are no-op stubs" claim (397 and 561 lines now), `verify --since`
  test coverage (`test_verify.py:298`, `:370`), jig's `DESIGN.md` M1-stub narrative, jig's
  PRODUCT.md "all five skills" framing, the stub-description section number, and the demo-README
  note.
- **2 were dropped** as unverifiable or working-as-intended: the plugin-loader truncation
  question, and the `sys.path.insert` boilerplate.
- **6 folded into existing issues** rather than becoming new ones: #211 (the uncommitted
  "ratified handoff" that `design-lint:12` and `plan-lint:9` both cite — the archaeology of C1),
  #197 (vocabulary dedup idioms), #201 (SHA-pin `actions/checkout@v4` + `setup-python@v5`, same
  privileged release job), #147 (PRODUCT.md `FILL IN` placeholders, telemetry cluster
  invisibility), #206 (the `_load_bearing.py` drift risk is the other half of the parser
  divergence), #218 (`coach/SKILL.md:26`'s pointer to a `DESIGN.md` risk list that no longer
  exists).
- **The rest promoted into 7 fix-scoped issues**: #222 (build-script CLI conventions) · #223
  (unbounded probe regex, git calls without `--`) · #224 (`evidence-capture --force` orphans) ·
  #225 (CLAUDE.md's two undocumented patterns, M9) · #226 (test-helper duplication) · #227
  (untested default timeout and cadence pause) · #228 (god-file watch, with the trend).

Several items had *worsened* since filing and are now recorded with numbers: `_normalize_ws` is
duplicated across 7 test files (was 4), and `skills/build/SKILL.md` is 616 lines (329 → 506 →
600 → 616 across three audits that each declined to split it).

### Net effect

| | Before | After |
|---|---|---|
| Open issues | 69 | 80 |
| Unmilestoned | 20 | 33 |
| Milestones | 13 | 13 (untouched — Phase 3 pending) |

The backlog got larger, deliberately. Five bags holding ~40 unactionable checkboxes became 7
issues that each name a fix; 11 real defects that were invisible are now filed.

Unmilestoned reconciles as 20 − 2 + 15 = 33: two of the seven closed issues (#163, #207) were
themselves unmilestoned, and 15 of the 18 new ones are.

**The three exceptions are deliberate.** #217, #218, and #225 went to M9 because all three are
prose-and-contract *guards* — the milestone's stated purpose — and M9 survives Phase 3's
proposal unchanged in scope (renamed "Contract & drift guards"). The other 15 are unmilestoned
because their proposed homes (M10, M11, M12) don't exist yet. #219, #220, and #221 carry the
`documentation` label but are structural hygiene rather than guards, so they wait with the rest.

That leaves 33 unmilestoned issues — now the largest bucket in the tracker, up from 20. Phase 3
is what resolves it, and it is still a proposal: no milestone was created, renamed, closed, or
reassigned by this pass.


---

## Execution record — Phase 3 (2026-07-25)

The re-roadmap was executed the same day, after the two judgment calls above were ratified.

### Milestones

**Created (4):** M10 — Post-merge flow coherence · M11 — Correctness & bug tail ·
M12 — Telemetry & outcome labels · Parked — evidence-gated.

**Renamed (3):** M5 "Close the loop (post-ship / X-series)" → "Post-ship outcome loop
(X-series)" (narrowed to Horizon-3 once telemetry moved to M12) · M6 "Gate cost & driver
reliability" → "Gate & build cost" · M9 "Contract & prose guards" → "Contract & drift guards"
(the guards are no longer only about prose). Descriptions rewritten to state each milestone's
sequencing rationale.

**Closed (8), all verified empty first:** M3, M4, M7, and all five `jig:` milestones. No
milestone was closed with an open issue in it — the script asserted `totalCount == 0` per
target and would have refused otherwise.

### Issues

All 80 open issues reassigned. Before writing anything, the script asserted that the plan
covered every open issue exactly once — no duplicates, no orphans, no assignments to closed
issues. It passed on the first run; 80 edits, zero failures.

| Milestone | Open |
|---|---|
| M10 — Post-merge flow coherence | 16 |
| M11 — Correctness & bug tail | 18 |
| M9 — Contract & drift guards | 13 |
| Parked — evidence-gated | 12 |
| M6 — Gate & build cost | 6 |
| M12 — Telemetry & outcome labels | 6 |
| M5 — Post-ship outcome loop (X-series) | 6 |
| M8 — Receipts & front door | 3 |

### Deviations from the proposed table

The Phase 3 table was written before the 18 new issues existed, so it named classes rather than
numbers in places. What actually landed, where it differs:

- **The 18 new issues slotted as:** #211–#216 and #219 → M10 · #220, #222, #223, #224, #226,
  #227 → M11 · #217, #218, #221, #225 → M9 · #228 → Parked (it is a watch item with stated
  entry conditions, which is exactly what Parked is for).
- **#147 moved M9 → M10.** The proposal listed it under M10 and it was in M9; PRODUCT.md's
  stale ground truth is a flow-coherence problem now that the file has to describe a build loop.
- **#190 stayed its own issue in M6** rather than being merged into #130. Whether to fold it is
  a scope call for whoever picks up the cost work; the correction comment on #190 recommends it
  but doesn't force it.

### Net effect

| | Start of cycle | After Phase 2 | After Phase 3 |
|---|---|---|---|
| Open issues | 69 | 80 | 80 |
| Open milestones | 13 | 13 | **8** |
| Named by origin | 6 | 6 | **0** |
| Unmilestoned | 20 | 33 | **0** |

Every milestone is now named for the work it serves. The five `jig:` buckets and M7 "The jig
seam" — the last places in the planning layer where the old repo boundary still existed — are
closed.

### What runs first

M10, then M11 in parallel with it, then M9, then M6, then M12, then M8, then M5. The rationale
is in the proposal above and restated in each milestone's description, so it survives without
this document. M10's first two issues (#211, #212) both carry ratified decisions and are ready
to build.
