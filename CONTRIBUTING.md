# Contributing to Studious

Thanks for your interest in improving Studious. Here's how to contribute.

## Reporting issues

Open an issue for bugs, unclear documentation, or suggestions. Include:

- What you expected to happen
- What actually happened
- Which command or agent was involved
- Your Claude Code version (`claude --version`)

## Proposing changes

1. **Open an issue first** for anything beyond a typo fix. Describe what you want to change and why. This saves everyone time if the change doesn't fit the project's direction.
2. **Fork and branch** from `main`.
3. **Make your changes.** Follow the patterns in existing files — agent frontmatter, command frontmatter, and directory structure are intentional.
4. **Open a PR** against `main` with a clear description of what changed and why.

## What makes a good contribution

- **Agent or command improvements** — better prompts, clearer instructions, more useful output formats
- **New agents or commands** that fit the existing workflow (gates, reviews, audits, backlog management)
- **Bug fixes** — commands that don't work as documented
- **Documentation** — README improvements, better examples

## Structure conventions

```
agents/       — Agent definitions (name, description, tools, model in frontmatter)
bin/          — Executables used by commands (e.g. gate-ledger for gate verdicts, /work-on's per-feature state, and /work-through's per-epic state)
commands/     — Slash commands (description, allowed-tools in frontmatter)
scripts/      — CI helper scripts (link checking, manifest validation)
skills/       — Natural-language trigger shims (skills/<name>/SKILL.md)
hooks/        — Shipped hook scripts + hooks.json (e.g. the PR-time gate reminder)
reference/    — Curated rubrics agents read at audit time (e.g. reference/idioms/<lang>.md)
templates/    — Scaffold files created by /studious-init
tests/        — Python and shell tests for commands and CI scripts
```

- Agents do the work. Commands orchestrate agents or provide standalone workflows.
- Skills are trigger shims: a tightly-scoped `description` lets a gate fire from natural language, and the body delegates to the matching command instead of duplicating it.
- Every agent and command reads PRODUCT.md, DESIGN.md, or CLAUDE.md for project context.
- Review reports save to `docs/studious/` subdirectories in the user's project, not to the plugin itself.
- Commands that produce output are recommend-only — they report, never modify external state (issues, PRs, files outside `docs/studious/`). **Exception:** the gate commands record their verdicts, and `/work-on` records per-feature flow position, to local, gitignored `.studious/` state in the consuming project; the ledger auto-appends `.studious/` to `.gitignore` on first write.
- **Workers never gate; gates never build.** `/work-through` dispatches worker agents (design docs, implementation, fixes) and gate agents (the existing gate commands) as separate agents with no shared context. A worker must never record a verdict; a gate agent must never write code. The `.studious/` exception above extends to `/work-through`: it records epic and story flow state to the same local, gitignored stores.

## Naming conventions

Names encode two things — whether something is an action or a role, and what scope it works at. Follow the existing shape; the prefix/suffix split is deliberate, not drift.

- **Commands are actions** — an action prefix plus its target: `gate-` (per-change checkpoints), `review-`/`deep-review` (periodic health), `extract-` (one-time scaffolding), `backlog-` (issue triage), `work-` (flow navigation: `work-on` one piece at a time, `work-through` a whole epic). The verb goes in front.
- **Agents are either a 1:1 reviewer or a role.** Periodic, project-scoped reviewers share their command's `review-*` name (currently spawned by `/deep-review`). Changeset specialists spawned by a fan-out command (`/gate-audit`, the gates) are named by role: `<domain>-auditor` for technical/rule checks (security, code, doc, architecture), `<domain>-reviewer` for human-judgment checks (product, ux, frontend).
- **One fan-out command, many subagents.** Parallel checks belong to subagents under a single entry point (`/gate-audit`, `/deep-review`), not to their own top-level commands. Don't add a command per check.
- **Skills are named for the intent they detect** — `evaluate-feature-idea`, `review-design-before-build`, `acceptance-check-before-merge` — not for the command they call. The `description` carries the trigger; keep it conservative (fire on explicit intent, list what it should NOT match) so a gate never interrupts when it isn't wanted.

## Model and effort assignments

Every agent carries two dispatch dials, and they move different multipliers. A dispatch's
cost is roughly `context × turns × model_rate`: **`model` moves the rate, `effort` moves the
turns.** Pin both by stakes, not by habit.

### `effort`

`low` · `medium` · `high` · `xhigh` · `max`, set in the agent's frontmatter, overriding the
session's effort. Lower effort means fewer and more-consolidated tool calls, less preamble,
and terser output — so it is the primary lever on turn count, which is where most of a
dispatch's tokens actually go (an agent's own prompt is ~1k tokens against tens of thousands
spent reading and reasoning).

- **`high`** — open-ended reasoning where a shallower pass ships a worse merge decision:
  `security-auditor`, `architecture-auditor`, `infra-auditor`, `operability-auditor`,
  `product-reviewer`, `review-architecture`, `review-product-health`, `review-security-health`.
- **`medium`** — judgment that is rubric-driven rather than open-ended, and periodic reviews:
  `code-auditor`, `test-auditor`, `frontend-reviewer`, `ux-reviewer`, `accessibility-auditor`,
  `premortem-auditor`, `dependency-auditor`, `prompt-auditor`, `review-codebase-health`,
  `review-interface-health`, `review-prompt-health`, `backlog-priorities`.
- **`low`** — mechanical, rule-based, or inventory work: `doc-auditor`, `review-readme`,
  `backlog-hygiene`.

**`effort` is model-gated, and on `haiku` there is nothing to gate.** Claude Code's
subagent frontmatter documents `effort`'s "available levels depend on the model", and
Haiku 4.5 does not take the parameter at all. So the `effort: low` pins on `review-readme`
and `backlog-hygiene` — both `model: haiku` — and the six `{model: 'haiku', effort:
'low'}` dispatches in `workflows/epic-driver.js` are declarations of intent, not live
dials: all eight items (those two agents plus the six dispatches) get haiku's own
behavior regardless. They are kept rather than deleted because they record the stakes
call and become live the moment either agent moves tier, but do not budget a turn-count
saving from them, and do not read the `low` row above as covering them. (A seventh
driver dispatch — the routing-scope probe, `workflows/epic-driver.js`'s
`resolveRoutingMatchFlags` — carries `effort: 'medium'` on the same `haiku` model for the
same reason: still inert, still a declaration of intent, not a live dial, however far
above `low` it's set — see that function's own comment for why it is pinned there
anyway.)

`premortem-auditor` sits at `medium` despite being merge-blocking: it verifies a fixed
register item by item and never free-hunts, so it is structured verification, not open-ended
reasoning. `dependency-auditor` sits at `medium` by the same argument: it enumerates per
changed dependency against a fixed rubric (advisory lookup, license, maintenance, drift)
rather than sweeping an open surface. `prompt-auditor` sits at `medium` by the same
argument again: it enumerates per changed prompt file against a fixed seven-dimension
rubric, and the lane fires often in LLM-native repos, so over-provisioning it would tax
most diffs. `accessibility-auditor` sits at `medium` by the same argument once more: it
walks each modified frontend file against the vendored checklist's four fixed sections
(keyboard access, contrast, focus management, semantic HTML) rather than an open-ended
sweep.

### `model`

`opus` when the core job is high-stakes reasoning or human judgment — where a weaker model
ships worse decisions.

- **`opus`** — security, architecture, operational, instruction-semantics, and product/UX
  judgment: `security-auditor`, `infra-auditor`, `operability-auditor`, `dependency-auditor`,
  `prompt-auditor`, `architecture-auditor`, `premortem-auditor`, `product-reviewer`,
  `ux-reviewer`, `accessibility-auditor`, `review-architecture`, `review-product-health`,
  `review-security-health`.
- **`sonnet`** — recommend-only synthesis and ranking judgment, no merge gate behind it:
  `backlog-priorities`, `review-codebase-health`, `review-interface-health`,
  `review-prompt-health`.
- **`haiku`** — recommend-only pure inventory and drift checks, no merge gate behind it:
  `backlog-hygiene`, `review-readme`.
- **Driver dispatches are a different pin surface, not an entry in the taxonomy above.**
  The `agent()` calls inside `workflows/epic-driver.js` carry their model as an inline
  call option, never as an agent's own frontmatter, so #136's "no silent default"
  principle governs them but the taxonomy's "no merge gate" framing does not — each is
  pinned for its own distinct reason, never one shared exception:
  - park/finale-ready/verify (`haiku`) are pure ledger/git read-backs and record-writes
    with no judgment threshold to get wrong — the same mechanical-fact-check posture as
    `ledgerScopeCheckPrompt`/`routingScopeCheckPrompt`.
  - merge (`haiku`) is different: it has one real judgment call inside it — whether a
    conflict's resolution is "mechanically obvious" — and stays `haiku` only because
    that threshold is asymmetric by design: its abort-biased default turns a wrong call
    into a safe park, never a bad merge (see the dispatch's own comment in
    `epic-driver.js`).
  - the fix-delta passes (`sonnet`) are a first-ever pin, not a drop from a previously-
    measured tier — the A/B rule below guards against dropping an already-measured
    tier, not against establishing a first one.
- **`inherit`** — merge-blocking, mechanical or rule-based checks, pending an A/B against a
  pinned drop (see below): `code-auditor`, `doc-auditor`, `test-auditor`,
  `frontend-reviewer`.

**`inherit` is a known defect, not a cheap tier — see [#136](https://github.com/jacquardlabs/studious/issues/136).** It resolves to the session model, so an
agent still pinned to it is billed at whatever the user happens to have selected: identical
to the `opus` tier in an Opus session, 2× that in a Fable one. Worse, it means the same
branch audited on two different days can be judged by two different models. The four agents
above are pinned to it only because they gate a merge and a model drop needs an A/B first —
they are not "the cheap tier" by design, they are the remaining defect. The five
`sonnet`/`haiku` agents above show the target shape: no merge gate behind an agent's output
means no A/B is needed to drop its tier, since a weak result is visible and cheap for a human
to catch. Do not add new `inherit` agents for that reason, and do not read `inherit`
anywhere in this file as an endorsed default. #136 also governs the unpinned driver dispatches listed above: walkthrough/story-fixer/worker/finale-fixer dispatches remain deliberately unpinned pending the A/B's outcome on their respective tiers.

**The A/B is `scripts/run_ab_eval.py`; the protocol is [`tests/ab/README.md`](tests/ab/README.md).**
It runs each arm over the golden fixtures N times and scores every planted defect as
reported, under-tiered, demoted to prose, or missed — a model drop is judged on *missed*,
the silent false negative this gate exists to catch, which a finding count cannot separate
from a demotion. `tests/ab/arms/model-drop-136.json` is the configured experiment, and the
six fixtures now plant a defect in each of the four agents' lanes, so all four can be
judged in one run — read the per-fixture rows rather than the aggregate.

Two levers move independently, and an A/B should vary one: pinning an explicit model ID
(`model: claude-opus-5`) removes the same-branch-judged-by-two-models defect without
changing tier or cost, and is separable from the question of whether the tier can drop.

## What we won't merge

- Changes that make agents modify issues, PRs, or external state without explicit user action
- Features that duplicate what [Superpowers](https://github.com/obra/superpowers) already handles (brainstorming, planning, TDD, execution)
- Agents that bundle multiple concerns (security + code quality in one agent) — each agent stays in its lane

## Code of conduct

Be respectful and constructive. We're all here to make better tools.
