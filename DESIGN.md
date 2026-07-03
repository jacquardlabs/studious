# Design system

<!-- This documents Studious's INTERFACE conventions — its user-facing surface, not how the
     code is written. Studious is a Claude Code plugin: its "interface" is the set of slash
     commands and their output contracts (verdict vocabularies, severity tiers, report
     structure), not a visual UI. Extracted by /extract-design-system; correct anything wrong. -->

## Surfaces

| Surface | Framework / tech | Entry point |
|---------|------------------|-------------|
| `plugin` | Claude Code plugin — Markdown commands, agents, skills + one hook | `.claude-plugin/plugin.json`; `commands/`, `agents/`, `skills/`, `hooks/` |

Studious has a single surface: a Claude Code plugin. It has no web UI, CLI binary, TUI, or
HTTP API. Output is GitHub-flavored markdown that Claude Code renders in the terminal.

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

| Command | Verdict tokens (canonical) | Source of truth | Consumers |
|---------|----------------------------|-----------------|-----------|
| `gate-should-we-build` | `BUILD` · `BUILD SMALLER` · `DEFER` · `DON'T BUILD` | `commands/gate-should-we-build.md` | skill `evaluate-feature-idea` |
| `gate-design-review` | `PROCEED TO PLAN` · `REVISE` · `RETHINK` | `commands/gate-design-review.md` | skill `review-design-before-build` |
| `gate-audit` | `PASS` · `FIX AND RE-AUDIT` · `NEEDS DISCUSSION` | `commands/gate-audit.md` | (no skill shim) |
| `gate-acceptance` | `SHIP` · `FIX AND RE-CHECK` · `HOLD` | `commands/gate-acceptance.md` | skill `acceptance-check-before-merge` |

Each vocabulary is three or four tokens: one "proceed," one "fix and retry," and (most)
one "stop/rethink." There is **no shared source-of-truth file** — every command defines its
own tokens inline, and the skill shims restate them. <!-- deviation: a single reference
listing all gate vocabularies would prevent a command and its skill drifting apart. -->

### Severity tiers

Findings across audits and reviews sort into three tiers, named consistently everywhere:
`Critical` · `Important` · `Track`. The canonical ladder and the per-auditor label→tier
mapping (e.g. `VISUAL BUG`, `BUG`, `PERFORMANCE`, `CLEANUP`, `SUGGESTION`, `INCONSISTENCY`,
`IMPROVEMENT`) live in `reference/severity-rubric.md`, cited by `commands/gate-audit.md`
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

## Per-surface conventions

### Plugin / prompt tooling

- **Command naming** — `verb`-prefixed families: `gate-*` (per-feature quality gates),
  `deep-review` (periodic reviews), `backlog-*` (issue triage), `extract-*` (context-doc
  population), `studious-init` (setup). All lowercase, hyphenated.
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
2. **No shared source for gate verdict vocabularies** — each command and its skill shim
   restate the tokens independently, so a command and its trigger can drift apart.
3. **`gate-audit` has no skill shim** while the other three gates do (`evaluate-feature-idea`,
   `review-design-before-build`, `acceptance-check-before-merge`) — natural-language access
   is inconsistent across the gate family.
