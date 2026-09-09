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
bin/          — Executables used by commands (e.g. gate-ledger for gate verdicts and /next's per-feature and per-epic state)
commands/     — Slash commands (description, allowed-tools in frontmatter)
scripts/      — CI helper scripts (link checking, manifest validation)
skills/       — Producer doors and model-invoked skills (skills/<name>/SKILL.md)
hooks/        — Shipped hook scripts + hooks.json (e.g. the PR-time gate reminder)
reference/    — Curated rubrics agents read at audit time (e.g. reference/idioms/<lang>.md)
templates/    — Scaffold files created by /setup
tests/        — Python and shell tests for commands and CI scripts
```

- Agents do the work. Commands orchestrate agents or provide standalone workflows.
- The natural-language shim layer is gone: commands and skills both carry a `description` field that makes them model-invocable by default, so a door's own `description` frontmatter carries its trigger phrasing and "Do NOT use for" exclusions directly — no separate `skills/<name>/` shim needed to fire it from plain language.
- Every agent and command reads PRODUCT.md, DESIGN.md, or CLAUDE.md for project context.
- Review reports save to `docs/studious/` subdirectories in the user's project, not to the plugin itself.
- **Recommend-only** is CLAUDE.md's invariant, not restated here — see CLAUDE.md's "Key invariants" bullets "Recommend-only means propose, never modify," "One bookkeeping boundary, not a name list," and "Everything else is either an executor or a human-typed one-off" for the exact boundary (any self-declared recommend-only command, the shared bookkeeping boundary, and the executor/one-off carve-out) and the predicate the `.studious/`/`docs/studious/` bookkeeping boundary applies — not an enumerated writer list.
- **Workers never gate; gates never build.** `/next` dispatches worker agents (design docs, implementation, fixes) and gate agents (the existing gate commands) as separate agents with no shared context. A worker must never record a verdict; a gate agent must never write code.
- **Code owns bookkeeping; prompts own judgment.** CLAUDE.md's invariant, restated here only because the verification rule below is its corollary — schedulers, ledgers, and cap math live in code; prompts carry decomposition, verdicts, and briefs.

### Verification belongs to scripts and inspectors, never to prompt prose

Verification is a mechanism, not an instruction. It belongs to **scripts** (`scripts/verify`, the CI jobs) and to **fresh-context inspectors** (the `/build` Inspector, the gauntlet judges) — never to self-check prose in a prompt. Do not write "double-check", "re-verify before responding", or "run it again to be sure" into `agents/`, `commands/`, `skills/`, or `reference/`. Gen-5 models already self-verify unprompted, so prose telling them to do it again buys nothing and bills the extra turns at output rates ([#302](https://github.com/jacquardlabs/studious/issues/302)). `tests/python/test_verification_invariant.py` guards the phrase list.

**Carve-out:** a Critical-challenge step that checks a finding's anchor against the diff is *judgment routing* — deciding which finding gets to move a verdict — not self-verification of the model's own output. It stays.

The sites #302 named, and what was decided about each:

| Site | Disposition | Why |
| --- | --- | --- |
| `reference/audit-compilation.md` — "Challenge every Critical before it can decide the verdict" | KEEP | The carve-out above. It runs on top of `report.py`'s ingest rules and routes uncertainty into filing rather than into re-reading (see `tests/ab/README.md`). |
| `reference/prompt-contract.md` §4 residual line | MOOT | Reporting language, not a self-check instruction. No door has stamped that file since #349, and #334 S4 deletes it. |
| `skills/task-execution-discipline/SKILL.md` Pillar 3 (verification-before-completion) | KEEP PENDING #188 | The one real deletion candidate. The decision record gates deletion on the golden-fixture replay harness ([#188](https://github.com/jacquardlabs/studious/issues/188), open) and a regression blocks it, so the prose stays; the citation in Pillar 3 is what a future deletion has to satisfy. |

## Naming conventions

Names encode two things — whether something is an action or a role, and what scope it works at. Follow the existing shape; the prefix/suffix split is deliberate, not drift.

- **Doors are the stages devs already know** — ten of them, declared in `reference/personas.md`: `bet`, `shape`, `build`, `review`, `ship`, `next`, `health`, `retro`, plus `setup` and `doctor`. Each names a stage from kanban, Scrum, XP, or Shape Up rather than a mechanism. Adding an eleventh means adding a charter row first; the CI check and the docs both derive from that table.
- **Agents are either a 1:1 reviewer or a role.** Periodic, project-scoped reviewers share the `review-*` name (only `review-outcomes` is still dispatched, by `/retro outcomes`; the other seven lost their dispatcher when `/health` moved to gauntlet's posture judges, and #334 S4 retires them). Changeset specialists spawned by a fan-out command (`/review`, the gates) are named by role: `<domain>-auditor` for technical/rule checks (security, code, doc, architecture), `<domain>-reviewer` for human-judgment checks (product, ux, frontend).
- **One fan-out command, many subagents.** Parallel checks belong to subagents under a single entry point (`/review`, `/health`), not to their own top-level commands. Don't add a command per check.
- **A door's trigger lives in its own `description`, not a separate shim.** Keep it conservative (fire on explicit intent, list what it should NOT match) so a door never interrupts when it isn't wanted. `reference/personas.md`'s `Backed by` column names the three `skills/` entries that are doors; the fourth, `task-execution-discipline`, is model-invoked but not a door.

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
  `review-security-health`, plus the four merge-blocking changeset auditors that used to
  sit at `inherit` — `code-auditor`, `doc-auditor`, `test-auditor`, `frontend-reviewer`.
  Those four carry the **full model ID `claude-opus-5`** rather than the `opus` alias:
  subagent frontmatter accepts either (`code.claude.com/docs/en/sub-agents`), and the ID
  is what makes the judgment reproducible across days rather than just same-tier — the
  defect #136 names is a *moving* judge, which an alias only half-closes. They are at the
  `opus` tier, not a dropped one; dropping them is #136's A/B half, still open.
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
  - the five that write or judge a story's own artifacts (`opus`) — the acceptance
    walkthrough, the story fixer, the build worker, the exorcise pass, and the finale
    fixer — were the last unpinned dispatches in the file. They are pinned at the tier
    they were already being handed in an Opus session, so this is a first pin at the
    observed tier, not a drop; they name the `opus` alias rather than a model ID because
    the Workflow `agent()` option is documented only as "overrides the model for this
    agent call" with no statement that a full ID resolves there, and a pin that silently
    fails to resolve is worse than the alias. Revisit if that API documents IDs.

**`inherit` is a known defect, not a cheap tier — see [#136](https://github.com/jacquardlabs/studious/issues/136), and nothing in this repo
carries it any more.** It resolves to the session model, so an agent pinned to it is billed
at whatever the user happens to have selected: identical to the `opus` tier in an Opus
session, 2× that in a Fable one. Worse, it means the same branch audited on two different
days can be judged by two different models — a judge that moves is not a gate. Do not add
new `inherit` agents, and do not read `inherit` anywhere in this file as an endorsed
default. The `sonnet`/`haiku` agents above show where a cheap tier is legitimately chosen:
no merge gate behind an agent's output means no A/B is needed to drop its tier, since a weak
result is visible and cheap for a human to catch.

**The A/B is `scripts/run_ab_eval.py`; the protocol is [`tests/ab/README.md`](tests/ab/README.md).**
It runs each arm over the golden fixtures N times and scores every planted defect as
reported, under-tiered, demoted to prose, or missed — a model drop is judged on *missed*,
the silent false negative this gate exists to catch, which a finding count cannot separate
from a demotion. `tests/ab/arms/model-drop-136.json` is the configured experiment, and the
six fixtures now plant a defect in each of the four agents' lanes, so all four can be
judged in one run — read the per-fixture rows rather than the aggregate.

Two levers move independently, and an A/B should vary one. The first — pinning an explicit
model ID (`model: claude-opus-5`) to remove the same-branch-judged-by-two-models defect
without changing tier or cost — is pulled: no agent is `inherit` any more. That leaves the
A/B a clean question, whether the tier can drop, on a fleet whose current tier is now a
fact rather than whatever session ran it. A **first** pin is not a drop and needs no A/B;
lowering an already-pinned merge-blocking agent's tier does.

## What we won't merge

- Changes that make agents modify issues, PRs, or external state without explicit user action
- Features that duplicate what [Superpowers](https://github.com/obra/superpowers) already handles (brainstorming, planning, TDD, execution)
- Agents that bundle multiple concerns (security + code quality in one agent) — each agent stays in its lane

## Code of conduct

Be respectful and constructive. We're all here to make better tools.
