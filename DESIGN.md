# Design system

<!-- This documents Studious's INTERFACE conventions — its user-facing surface, not how the
     code is written. Studious is a Claude Code plugin: its "interface" is the set of slash
     commands and their output contracts (verdict vocabularies, severity tiers, report
     structure), not a visual UI. Extracted by /setup; correct anything wrong. -->

## Surfaces

| Surface | Framework / tech | Entry point |
|---------|------------------|-------------|
| `plugin` | Claude Code plugin — Markdown commands, agents, skills + one hook | `.claude-plugin/plugin.json`; `commands/`, `agents/`, `skills/`, `hooks/` |
| `board-ui` | Local, read-only web board over one epic's `/next` state — stdlib-only Python HTTP+SSE server, one self-contained HTML/CSS/JS document, no build step, no external requests | `bin/board-server EPIC_SLUG [--open]`; `assets/board-ui/` |

Studious's primary surface is a Claude Code plugin: no build step, no runtime app, output
is GitHub-flavored markdown that Claude Code renders in the terminal. `board-ui` is a
narrow, opt-in exception — a local dev instrument (`GET /state`, `GET /events`, `GET /`;
`reference/board-schema.md`) for watching one `/next` epic run live. It binds to
`127.0.0.1` only, has no write endpoint, and reads only the same `.studious/epics/`
files `gate-ledger` already writes durably — it does not turn Studious into a service.

## Semantic palette

Not applicable as color — the plugin emits markdown and does not control terminal styling.
State is conveyed through **verdict tokens** and **severity tiers** (below), and emphasis
through bold. The single styling convention: verdict tokens and tier names render **bold**
(`**BUILD**`, `**Critical**`).

## Vocabulary

The plugin's most important interface contract. Each gate command emits a fixed set of
verdict tokens; the natural-language skill shims trigger the same commands and must report
the same tokens.

### Gate verdict vocabularies

| Episode | Command | Verdict tokens (canonical) | Source of truth | Consumers |
|---------|---------|----------------------------|-----------------|-----------|
| bet | `gate-should-we-build` | `BUILD` · `BUILD SMALLER` · `DEFER` · `DON'T BUILD` | `commands/bet.md` | skill `evaluate-feature-idea` · `/next` |
| design | `gate-design-review` | `PROCEED TO PLAN` · `REVISE` · `RETHINK` | `commands/review.md` | skill `review-design-before-build` · `/next` |
| work | `gate-audit` | `PASS` · `FIX AND RE-REVIEW` · `NEEDS DISCUSSION` | `commands/review.md` | `/next` (no skill shim) |
| delivery | `gate-acceptance` | `SHIP` · `FIX AND RE-REVIEW` · `HOLD` | `commands/review.md` | skill `acceptance-check-before-merge` · `/next` |

Each vocabulary is three or four tokens: one "proceed," one "fix and retry," and (most)
one "stop/rethink." The canonical listing and per-gate breakdown now live in
`reference/gate-vocabulary.md`, cited by `commands/next.md` rather than restated there —
this table should mirror that file, not diverge from it.

### Build-execution vocabularies

The gate vocabularies above judge work; these describe producing it. Absorbed with jig
(#150) — every row's source of truth is the skill's own `SKILL.md`.

| Concept | Canonical display | Source of truth | Consumers |
|---------|-------------------|-----------------|-----------|
| `/shape` verdict | `DESIGNED` \| `NEEDS RESEARCH` \| `REVISED` | `skills/shape/SKILL.md` (verdict table) | `/shape` output; read by `/build` and `/review` |
| `/build` verdict | `PLAN READY` \| `DESIGN GAP` \| `TOO BIG` | `reference/planning-contract.md` (verdict table) | `/build` output; `DESIGN GAP` routes back to `/shape` |
| `/build` task status | `todo` → `in-progress` → `PASS`/`REPLAN`/`ESCALATE` | `skills/build/SKILL.md` | flipped by scripts only, never the model |
| `/build` failure-routine action | `FIX` \| `RESAMPLE` | `skills/build/SKILL.md` | the Foreman's own per-attempt judgment call after an item FAIL; transient, never written as a task status suffix |
| `/build` session verdict | `BUILT` \| `PAUSED` \| `ESCALATED` | `skills/build/SKILL.md` (verdict table) | reported to the coach, the human, and `gate-ledger` |
| inspector verdict | `CLEAR` \| `DEFECT` \| `CONCERN` | `skills/build/SKILL.md` (step 2.6) | `/build`'s failure routine; `CONCERN` forwards to `/review` |
| `/ship` verdict | `MERGE` \| `PR` \| `KEEP` \| `DISCARD` | `skills/ship/SKILL.md` (verdict table) | closes out a build branch |
| checkpoint item type | `cap` \| `hold` | `reference/planning-contract.md` (checkpoint block template) | every checkpoint block in `PLAN.md` |
| verification tier | `script` \| `test-backed` \| `probe` | `reference/planning-contract.md` (checkpoint block template) | every checkpoint item; no `judgment` tier permitted |
| risk tag | `LOW` \| `REPLAN-RISK` \| `ESCALATE-RISK` | `reference/planning-contract.md` (Risk tagging) | assigned by `/build`, consumed by `/build`'s cadence/pause logic |

**`PASS` means two different things and the collision is deliberate-adjacent, not
resolved.** A `/build` task status `PASS` is a `PLAN.md` heading suffix written by
`scripts/status-flip`; a `gate-audit` `PASS` is a gate verdict in the ledger. Name which
one you mean whenever both could be read — tracked as #174.

### Severity tiers

Findings across audits and reviews sort into three tiers, named consistently everywhere:
`Critical` · `Important` · `Track`. The canonical ladder and the per-auditor label→tier
mapping (e.g. `VISUAL BUG`, `BUG`, `PERFORMANCE`, `CLEANUP`, `SUGGESTION`, `INCONSISTENCY`,
`IMPROVEMENT`) live in `reference/severity-rubric.md`, cited by `commands/review.md`
rather than restated there. `deep-review` and the `review-*` agents already emit directly
in this vocabulary and need no mapping.

The shared audit/review posture — injection-defense, read-only/diff-scope, output-row
schema, and the calibrate-don't-suppress closer — lives in `reference/prompt-contract.md`,
cited by the auditor/reviewer agents rather than restated per-agent.

## Formatting

- **Report structure** — Summary first, then findings grouped by severity tier (Critical →
  Important → Track), then a final **Verdict** line carrying one of the command's
  verdict tokens. Used by `gate-audit`, `gate-acceptance`, and the review agents.
- **Summary line** — "one line per auditor/review: name, findings by severity, pass/fail."
- **Report file paths** — periodic reviews write to `docs/studious/<area>-reviews/YYYY-MM-DD-<area>-review.md`.
- **The checkpoint block** is the build side's closest analog to a type scale — a fixed
  template every task in `PLAN.md` follows: `Why now` / `Read first` / `Rests on` / `Do` /
  `Not here` / `Done means` (numbered cap/hold items with a verification tier) /
  `Evidence`. Every block: ≥1 cap, ≥1 hold, ≤5 items total.
- **The tier parenthetical's own internal shape** (`scripts/plan-lint`): the tier word
  itself, and, for `script` / `test-backed` items only, a backtick-quoted repo-relative
  method path immediately after it — a `probe` item carries no path, since there's no
  pre-existing repo file to name for a live-observed artifact:

  ```
  Done means:
  1. [cap|hold]  <behavior text>          (tier: script `scripts/plan-lint`)
  2. [cap|hold]  <behavior text>          (tier: test-backed `tests/jig/test_plan_lint.py`)
  3. [cap|hold]  <behavior text>          (tier: probe)
  ```

  A backtick span anywhere in a checkpoint block (a `Read first:` pointer, a tier's
  method path, a `[cap]` item's own behavior text on a LOAD-BEARING task) is the plan
  author's explicit signal that a token is concrete and checkable, not narrative —
  `scripts/plan-lint` treats prose outside backticks as unchecked by design.
- **Design doc structure** (`reference/design-doc-contract.md` — the sole authority): 8
  required sections, each tied to a named downstream consumer (Problem & persona, Proposed
  design, User journey, Out of scope, Alternatives considered, Success metrics, Operational
  readiness, Open questions — see `skills/shape/SKILL.md` Step 4 for the section→consumer
  table). A doc may carry sections beyond these; `scripts/design-lint` enforces the floor,
  not an exact count.
- **Task calibration**: `/build` produces 3–8 tasks per plan; <3 is too big to verify, >8
  is fragmenting or the feature itself is `TOO BIG`.
- **PR evidence table**: `/ship` promotes each task's Done-means into the PR body as
  item → verification method → evidence link → pass.

## Per-surface conventions

### Plugin / prompt tooling

- **Command naming** — `verb`-prefixed families: `gate-*` (per-feature quality gates),
  `deep-review` (periodic reviews), `backlog-*` (issue triage), `extract-*` (context-doc
  population), `studious-init` (setup), `work-on` (feature-flow navigation). All lowercase, hyphenated.
- **Frontmatter** — commands carry `description` + `allowed-tools`; agents carry `name` +
  `description` + `tools` + `model`. Descriptions are one line, imperative.
- **Skills as trigger shims** — `skills/<name>/SKILL.md` holds a tightly-scoped `description`
  so a gate fires from natural language; the body delegates to the matching command rather
  than duplicating it. Triggers are deliberately conservative.
- **Agents do the work; commands orchestrate** — auditors/reviewers are single-purpose
  agents (`agents/*.md`) spawned in parallel; commands compose them and synthesize results.
- **Propose, never apply** — reviews emit proposed diffs to context docs; they never write
  them. The human approves.

## Model assignments

Pin by stakes, not by habit. An agent's `model` is `opus` when its core job is high-stakes
reasoning or human judgment — where a weaker model ships worse decisions — and `inherit`
(the session model) for mechanical, rule-based, or inventory work. Don't pin to a bare tier
like `sonnet` — use `inherit` so the agent tracks the user's session model. Full policy and
the current per-agent assignments live in `CONTRIBUTING.md` §Model assignments; this section
documents the policy for the interface surface, it does not restate the per-agent list.

## Anti-patterns (do NOT do these)

<!-- Fill in based on intent. Candidates surfaced during extraction, for your judgment:
     - Never define a gate's verdict tokens in the skill shim independently of the command.
     - Never introduce a fourth severity tier; map into the existing three.
     - Never have an agent apply changes to context docs — propose only. -->

---

## Top inconsistencies (extraction findings)

1. ~~**Third severity tier is named two ways** — `Minor` in `gate-audit`, `Track` in
   `deep-review` and the review agents. Same concept, two labels.~~ Resolved: unified on
   `Track` everywhere; the canonical ladder and per-auditor mapping now live in
   `reference/severity-rubric.md`.
2. **No shared source for gate verdict vocabularies** — partially addressed: the canonical
   listing now lives in `reference/gate-vocabulary.md`, and `/next` cites it rather than
   restating token definitions. The three skill shims still restate their gate's tokens
   independently in a one-line summary and haven't been repointed at the reference file yet.
3. **`gate-audit` has no skill shim** while the other three gates do (`evaluate-feature-idea`,
   `review-design-before-build`, `acceptance-check-before-merge`) — natural-language access
   is inconsistent across the gate family.
