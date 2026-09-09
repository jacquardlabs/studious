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
bin/          — Executables used by commands (e.g. gate-ledger for gate verdicts and /next's per-feature state)
commands/     — Slash commands (description, allowed-tools in frontmatter)
scripts/      — CI helper scripts (link checking, manifest validation)
skills/       — Producer doors and model-invoked skills (skills/<name>/SKILL.md)
hooks/        — Shipped hook scripts + hooks.json (evidence capture, session-start heads-up)
reference/    — Contracts and rubrics the doors read (e.g. reference/severity-rubric.md)
templates/    — Scaffold files created by /setup
tests/        — Python and shell tests for commands and CI scripts
```

- Agents do the work. Commands orchestrate agents or provide standalone workflows.
- The natural-language shim layer is gone: commands and skills both carry a `description` field that makes them model-invocable by default, so a door's own `description` frontmatter carries its trigger phrasing and "Do NOT use for" exclusions directly — no separate `skills/<name>/` shim needed to fire it from plain language.
- Every agent and command reads PRODUCT.md, DESIGN.md, or CLAUDE.md for project context.
- Review reports save to `docs/studious/` subdirectories in the user's project, not to the plugin itself.
- **Recommend-only** is CLAUDE.md's invariant, not restated here — see CLAUDE.md's "Key invariants" bullets "Recommend-only means propose, never modify," "One bookkeeping boundary, not a name list," and "Everything else is either an executor or a human-typed one-off" for the exact boundary (any self-declared recommend-only command, the shared bookkeeping boundary, and the executor/one-off carve-out) and the predicate the `.studious/`/`docs/studious/` bookkeeping boundary applies — not an enumerated writer list.
- **Workers never gate; gates never build.** Producers (`/shape`, `/build`) and judges (`/review`'s gauntlet lanes) run as separate agents with no shared context. A worker must never record a verdict; a gate agent must never write code.
- **Code owns bookkeeping; prompts own judgment.** CLAUDE.md's invariant, restated here only because the verification rule below is its corollary — schedulers, ledgers, and cap math live in code; prompts carry decomposition, verdicts, and briefs.

### Verification belongs to scripts and inspectors, never to prompt prose

Verification is a mechanism, not an instruction. It belongs to **scripts** (`scripts/verify`, the CI jobs) and to **fresh-context inspectors** (the `/build` Inspector, the gauntlet judges) — never to self-check prose in a prompt. Do not write "double-check", "re-verify before responding", or "run it again to be sure" into `agents/`, `commands/`, `skills/`, or `reference/`. Gen-5 models already self-verify unprompted, so prose telling them to do it again buys nothing and bills the extra turns at output rates ([#302](https://github.com/jacquardlabs/studious/issues/302)). `tests/python/test_verification_invariant.py` guards exactly that list, as case-insensitive substrings: `("double-check", "re-verify before", "run it again to be sure")` — the second is truncated so it catches "re-verify before responding" and every variant of what follows.

**Carve-out:** a Critical-challenge step that checks a finding's anchor against the diff is *judgment routing* — deciding which finding gets to move a verdict — not self-verification of the model's own output. It stays.

The sites #302 named, and what was decided about each:

| Site | Disposition | Why |
| --- | --- | --- |
| `reference/audit-compilation.md` — "Challenge every Critical before it can decide the verdict" | KEEP | The carve-out above. It runs on top of gauntlet's `scripts/report.py` ingest rules and routes uncertainty into filing rather than into re-reading (see `tests/ab/README.md`). |
| `skills/task-execution-discipline/SKILL.md` Pillar 3 (verification-before-completion) | KEEP PENDING #188 | The one real deletion candidate. Deletion is gated on the golden-fixture replay harness ([#188](https://github.com/jacquardlabs/studious/issues/188), open): a regression there — a fresh executor filling `Evidence` less honestly without the prose — would block it. Nothing has run yet, so the prose stays and this row, not the pillar itself, is the gate a future deletion has to satisfy. |

## Naming conventions

Names encode two things — whether something is an action or a role, and what scope it works at. Follow the existing shape; the prefix/suffix split is deliberate, not drift.

- **Doors are the stages devs already know** — ten of them, declared in `reference/personas.md`: `bet`, `shape`, `build`, `review`, `ship`, `next`, `health`, `retro`, plus `setup` and `doctor`. Each names a stage from kanban, Scrum, XP, or Shape Up rather than a mechanism. Adding an eleventh means adding a charter row first; the CI check and the docs both derive from that table.
- **Three local agents, named for their job.** `review-outcomes` (dispatched by `/retro outcomes`), `backlog-priorities` (`/bet`), and `backlog-hygiene` (`/health backlog`) are the only files in `agents/`; every judge lane is a `gauntlet:<judge>` dispatch, named by gauntlet's charter.
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
dispatch's tokens actually go.

- **`medium`** — `backlog-priorities`: ranking judgment over a fixed backlog.
- **`low`** — `review-outcomes`, `backlog-hygiene`: mechanical, rule-based, or inventory
  work. (`backlog-hygiene` is `haiku`, which does not take the parameter — the pin records
  the stakes call and becomes live if the agent moves tier.)

Gauntlet's judges pin their own `model` and `effort` in gauntlet's frontmatter; nothing here
overrides them.

### `model`

`opus` when the core job is high-stakes reasoning or human judgment — where a weaker model
ships worse decisions. None of the three local agents gates a merge, so none needs it:

- **`sonnet`** — `backlog-priorities`, `review-outcomes`: recommend-only synthesis and
  ranking judgment.
- **`haiku`** — `backlog-hygiene`: recommend-only inventory and drift checks.

**`inherit` is a known defect, not a cheap tier — see [#136](https://github.com/jacquardlabs/studious/issues/136), and nothing in this repo
carries it any more.** It resolves to the session model, so an agent pinned to it is billed
at whatever the user happens to have selected: identical to the `opus` tier in an Opus
session, 2× that in a Fable one. Worse, it means the same branch audited on two different
days can be judged by two different models — a judge that moves is not a gate. Do not add
new `inherit` agents, and do not read `inherit` anywhere in this file as an endorsed
default. The `sonnet`/`haiku` agents above show where a cheap tier is legitimately chosen:
no merge gate behind an agent's output means no A/B is needed to drop its tier, since a weak
result is visible and cheap for a human to catch.

Lowering a merge-blocking judge's tier is gauntlet's call, made with an A/B in that repo; a
local agent's tier can move on a human's read of its output, since nothing merges on it.

## What we won't merge

- Changes that make agents modify issues, PRs, or external state without explicit user action
- Features that duplicate what [Superpowers](https://github.com/obra/superpowers) already handles (brainstorming, planning, TDD, execution)
- Agents that bundle multiple concerns (security + code quality in one agent) — each agent stays in its lane

## Code of conduct

Be respectful and constructive. We're all here to make better tools.
