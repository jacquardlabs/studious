# Design system

jig is a Claude Code plugin — its user-facing surface is the set of
commands/skills it exposes and the vocabulary they emit, not a visual UI.
**M1–M6 have all shipped** (current release v1.6.0): `.claude-plugin/plugin.json`
and `skills/{design,plan,build,finish,coach,task-execution-discipline}/`
all exist, each user-invoked skill carrying a real `SKILL.md` with its own
verdict vocabulary, not a stub. Everything below is extracted from the
shipped `SKILL.md` files themselves, not the handoff document — each is now
its own source of truth. Re-run `/extract-design-system` after a future
milestone changes a skill's verdict vocabulary or adds a new surface.

## Surfaces

| Surface | Framework / tech | Entry point |
|---------|------------------|-------------|
| `plugin` | Claude Code plugin (skills + deterministic scripts) | Shipped — `skills/design`, `skills/plan`, `skills/build`, `skills/finish`, `skills/coach`, and `skills/task-execution-discipline` all carry real `SKILL.md` behavior (M1–M6). 8 deterministic scripts back them: `design-lint`, `plan-lint`, `verify`, `status-flip`, `evidence-capture`, `evidence-freshness`, `build-report`, and `worktree-setup` — all zero-model structural checks with deterministic exit codes, per this doc's Formatting section above. |

## Semantic palette

No color/terminal-style palette exists — jig's plugin surface renders as
plain text inside Claude Code's chat interface, not a styled terminal or web
UI. The functional equivalent of "state → style" here is the closed verdict
vocabulary each command emits (see Vocabulary and Plugin/prompt tooling
below) — state is signaled by which token a command returns, not by color.

## Vocabulary

The canonical verdict enums each shipped command commits to. Every row's
source of truth is now the skill's own `SKILL.md` — the handoff document
that originally ratified these is historical context, not the live
reference.

| Concept | Canonical display | Source of truth | Consumers |
|---------|-------------------|-----------------|-----------|
| `/design` verdict | `DESIGNED` \| `NEEDS RESEARCH` \| `REVISED` | `skills/design/SKILL.md` (verdict table) | `/design` output; read by `/plan` and studious's `/gate-design-review` |
| `/plan` verdict | `PLAN READY` \| `DESIGN GAP` \| `TOO BIG` | `skills/plan/SKILL.md` (verdict table) | `/plan` output; `DESIGN GAP` routes back to `/design` |
| `/build` task status | `todo` → `in-progress` → `PASS`/`REPLAN`/`ESCALATE` | `skills/build/SKILL.md` | flipped by scripts only, never the model |
| `/build` failure-routine action | `FIX` \| `RESAMPLE` | `skills/build/SKILL.md` | the Foreman's own per-attempt judgment call after an item FAIL; transient, never written as a task status suffix |
| `/build` session verdict | `BUILT` \| `PAUSED` \| `ESCALATED` | `skills/build/SKILL.md` (verdict table) | reported to the coach and the human |
| inspector verdict | `CLEAR` \| `DEFECT` \| `CONCERN` | `skills/build/SKILL.md` (step 2.6) | `/build`'s failure routine; `CONCERN` forwards to `/gate-audit` |
| `/finish` verdict | `MERGE` \| `PR` \| `KEEP` \| `DISCARD` | `skills/finish/SKILL.md` (verdict table) | closes out a build branch |
| checkpoint item type | `cap` \| `hold` | `skills/plan/SKILL.md` (checkpoint block template) | every checkpoint block in `PLAN.md` |
| verification tier | `script` \| `test-backed` \| `probe` | `skills/plan/SKILL.md` (checkpoint block template) | every checkpoint item; no `judgment` tier permitted |
| risk tag | `LOW` \| `REPLAN-RISK` \| `ESCALATE-RISK` | `skills/plan/SKILL.md` (Risk tagging) | assigned by `/plan`, consumed by `/build`'s cadence/pause logic |

## Formatting

- **The checkpoint block** (handoff §4) is jig's closest analog to a type
  scale — a fixed template every task in `PLAN.md` follows: `Why now` / `Read
  first` / `Rests on` / `Do` / `Not here` / `Done means` (numbered cap/hold
  items with a verification tier) / `Evidence`. Every item: ≥1 cap, ≥1 hold,
  ≤5 items total.
- **The tier parenthetical's own internal shape** (`scripts/plan-lint`, story
  plan-lint, issue #12): the tier word itself, and, for `script` /
  `test-backed` items only, a backtick-quoted repo-relative method path
  immediately after it — a `probe` item carries no path, since there's no
  pre-existing repo file to name for a live-observed artifact:

  ```
  Done means:
  1. [cap|hold]  <behavior text>          (tier: script `scripts/plan-lint`)
  2. [cap|hold]  <behavior text>          (tier: test-backed `tests/test_plan_lint.py`)
  3. [cap|hold]  <behavior text>          (tier: probe)
  ```

  A backtick span anywhere in a checkpoint block (a `Read first:` pointer, a
  tier's method path, a `[cap]` item's own behavior text on a LOAD-BEARING
  task) is the plan author's explicit signal that a token is concrete and
  checkable, not narrative — `scripts/plan-lint` treats prose outside
  backticks as unchecked by design.
- **Design doc structure** (`reference/design-doc-contract.md`, ratified by
  story `design-skill`/issue #8's own design doc, Proposed design → Step 4
  fork): exactly 7 sections, each tied to a named downstream consumer
  (Problem & persona, Proposed design, User journey, Out of scope,
  Alternatives considered, Operational readiness, Open questions — see
  `skills/design/SKILL.md` Step 4 for the section→consumer table). This
  supersedes the handoff §5.1 step 4 wording this bullet previously carried
  (Intent, Experience, Contracts, Approach, Assumptions, Not doing, Risks):
  every design doc this project has actually shipped and gate-reviewed uses
  the seven named here, not the handoff's, and `/design` itself drafts
  against these names.
- **Task calibration**: `/plan` produces 3-8 tasks per plan; <3 is too big to
  verify, >8 is fragmenting or the feature itself is `TOO BIG`.
- **PR evidence table** (handoff §5.4): promotes each task's Done-means into
  the PR body as item → verification method → evidence link → pass.

## Per-surface conventions

### Plugin / prompt tooling

- **Command naming**: single verb, slash-prefixed — `/design`, `/plan`,
  `/build`, `/finish`, and (decided at M6, story coach-skill, issue #21)
  `/coach`. The coach is a user-invoked skill triggering on an explicit ask
  only — never auto-triggering on a verdict token earlier in the
  conversation; `skills/coach/SKILL.md` is its source of truth (see risk #4
  below, now closed).
- **Verdict vocabulary**: see the Vocabulary table above — each command owns
  a distinct enum with no reused tokens *within jig itself*. One
  cross-project watch-item: jig's `/build` task-status token `PASS` and
  studious's own gate-verdict `PASS` (used across `/gate-audit` etc.) are the
  same word for a related-but-distinct concept (a task passing verification
  vs. a gate passing judgment). Not a conflict today since they never appear
  in the same table, but worth explicit disambiguation once both surfaces
  are visible together in a PR body (jig's `/finish` promotes Done-means
  into the PR; studious's gates also report there).
- **Severity/tier vocabulary**: jig's risk tags (`LOW`/`REPLAN-RISK`/
  `ESCALATE-RISK`) are a deliberately different vocabulary from studious's
  report tiers (Critical/Important/Track) — different axis (plan-time risk
  vs. review-time severity), not meant to align. Worth a note in CLAUDE.md
  once both appear in the same operator-facing surface (e.g. a joint
  changelog), so the distinction doesn't read as an inconsistency.
- **Report/output structure**: see Formatting above — the checkpoint block
  and PR evidence table are the two structural conventions that exist so
  far.
- **Session prose style**: all user-facing prose generated during a jig session — status updates, verdict messages, issue draft previews, decision patch explanations — follows four rules: (1) open on substance, no preamble; (2) one sentence per task status update; (3) verdict lines are terminal — bold token, one sentence of rationale, nothing after; (4) bullets over paragraphs when listing 2+ items.
- **Review-consumption rule for generated artifacts**: every artifact a human reviews section-by-section or card-by-card in viva — a design doc's `##` sections, a `PLAN.md` task block — is written to be judged on one screen: the section or field's first sentence carries its claim or decision, enumerable content is bulleted, and nothing pads a card the reviewer must scroll past to approve.

## Anti-patterns (do NOT do these)

<!-- Left empty per the extraction process — this needs your intent, not an
     assumption. Candidates worth ruling on: reusing a gate token (PASS,
     etc.) for a jig-internal concept with different meaning; inventing a
     visual palette before any surface actually renders visually. -->

---

## Top inconsistencies / risks if left unaddressed

1. **No behavioral surface existed to extract from** — **closed**: M1's
   stub `SKILL.md` files (this risk's original concern) were replaced by
   real behavior across M2–M6. This document is now sourced from the
   shipped `SKILL.md` files, and the Vocabulary table's "source of truth"
   column points there instead of the handoff (see #56, #74).
2. **`PASS` token collision risk** — jig's task-level `PASS` and studious's
   gate-level `PASS` are different concepts sharing a word; low risk today,
   real risk once both appear in the same PR. Tracked as
   [#75](https://github.com/jacquardlabs/jig/issues/75).
3. **Risk-tag vs. severity-tier vocabulary divergence** — intentional, but
   undocumented anywhere a human would see both systems side by side.
4. **Coach invocation convention unspecified** — **closed at M6** (story
   coach-skill, issue #21): the coach is `/coach`, the same single-verb
   slash-prefixed convention as the other four commands, user-invoked on an
   explicit ask only. `skills/coach/SKILL.md` now carries the convention
   and the orchestration behavior behind it; it emits no verdict enum of
   its own (its closed vocabulary is its recommendation action set), so no
   Vocabulary-table row was added.
5. **No palette or formatting convention exists for a future non-chat
   surface** (e.g. a report or CLI wrapper) — not needed today, but the
   handoff doesn't rule one out either, so this doc would need a real
   Surfaces-table addition if one is ever added.
