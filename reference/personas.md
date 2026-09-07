# Persona charter — the doors, who owns them, and what each may do

Canonical source for Studious's command surface and the lane rule that keeps it honest.
This file is **data**: the tables below are parsed by `scripts/check_gate_independence.py`
to derive the guarded surface, and by `tests/python/test_persona_charter.py` to assert the
prose surfaces agree. Change a door here first, then change the door.

**The test is residency, not vocabulary.** A persona is a charter plus durable records —
never a resident agent. Every agent in `agents/` is dispatched fresh, judges once, and
exits; naming the roles below creates no standing ones.

## Doors

Ten doors, eight of them day-to-day. The `Class` column is load-bearing: it is what
`check_gate_independence.py` reads to decide which files it guards and which command
names count as producer invocations.

A door is backed by a `commands/*.md` file or a `skills/*/SKILL.md` file — both are
invokable slash commands, and which one backs a door is an implementation detail, not a
class distinction. The `Backed by` column is the authority either way.

**There is no separate natural-language shim layer.** Commands and skills both carry a
`description` field that makes them model-invocable by default (verified against the
installed Claude Code docs, 2026-09-06); a door's own `description` frontmatter does
everything a `skills/<name>/` trigger shim used to. The five natural-language shims that
once fronted `/doctor`, `/next`, `/bet`, `/retro`, and `/review` had their trigger
phrasing and "Do NOT use for" exclusions folded into that target door's `description`,
then their directories were deleted; `skills/` now holds only
the three producer doors and `task-execution-discipline` (model-invoked, not a door).

**`Absorbed` lists names that are gone**, so `/doctor` can grep a consuming project for
them and flag stale hits. `/build` absorbed `/plan` but kept its own name, so `build` is
excluded from its own Absorbed cell — including it would make `/doctor` flag every live
`/build` mention.

| Door | Persona | Class | Backed by | Absorbed |
|---|---|---|---|---|
| `/bet` | Product Owner | judge | `commands/bet.md` | gate-should-we-build, backlog-priorities |
| `/shape` | Designer | producer | `skills/shape/SKILL.md` | design |
| `/review` | Design Reviewer, Reviewer | judge | `commands/review.md` | gate-design-review, gate-audit, gate-acceptance |
| `/build` | Builder | producer | `skills/build/SKILL.md` | plan |
| `/ship` | Shipper | producer | `skills/ship/SKILL.md` | finish, handback |
| `/next` | Navigator, Orchestrator | navigator | `commands/next.md` | work-on, work-through, coach |
| `/health` | Health Officer | periodic | `commands/health.md` | deep-review, backlog-hygiene |
| `/retro` | Retrospective Lead | periodic | `commands/retro.md` | review-outcomes |
| `/setup` | — | infra | `commands/setup.md` | studious-init, extract-product-context, extract-design-system |
| `/doctor` | — | infra | `commands/doctor.md` | studious-doctor |

### Bare names and collisions

A bare door name resolves only while nothing else claims it. Claude Code built-ins win
over plugin commands, and `/doctor` collides today (Claude Code ships its own `/doctor`);
any other name can collide tomorrow with a new built-in or another installed plugin. The
namespaced form is always unambiguous: `/studious:doctor`, `/studious:review`,
`/studious:<door>`. When actionable text tells a human to run a door whose bare name is
known to collide, write the namespaced form — a copy-pasted command that runs the wrong
tool is worse than a longer one (the same finding #257 hit with the old bare `/design`).

### What each class may do

- **judge** — records verdicts. May never invoke a producer door or require a producer's
  private artifact — a gate judges the work, never who produced it (enforced by
  `scripts/check_gate_independence.py`); `reference/worker-contract.md` is the
  executor-agnostic contract a judge may rely on instead.
- **producer** — writes and commits code, docs, and evidence. May name other producers and
  may *convene* a judge at its own exit (`/shape` the design episode, `/build` the work
  episode, `/ship` the delivery episode), but may never write a verdict. Convening is not
  judging.
- **navigator** — does neither. `/next` reads position, proposes the next door, and runs it
  only on confirmation. It routes to producers and convenes judges, so it is deliberately
  off the guarded surface; what bounds it is the episode round cap in `bin/gate-ledger`,
  not this rule.
- **periodic** — recommend-only whole-project reviews. Writes reports to `docs/studious/`,
  gates no merge, and is off the guarded surface for the same reason a navigator is: it
  names producers as ordinary product advice.
- **infra** — rare one-off entrypoints the human types themselves. Off the guarded surface.

`workflows/epic-driver.js`, `hooks/*.sh`, `bin/gate-ledger`, and every file in `agents/`
are guarded regardless of door, because they carry judgment machinery no door owns
outright. `epic-driver.js` holds both roles at once and marks its dispatch half with the
worker-dispatch sentinels the check already understands.

## Episodes

A door convenes an episode; the episode's verdict tokens live in
`reference/gate-vocabulary.md`, which stays the authority for tokens. This table maps the
episode to the door that convenes it, and nothing else.

| Episode | Convened by | Also convened by |
|---|---|---|
| bet | `/bet` | `/next` (on confirmation) |
| design | `/review` | `/shape`, `/next` (on confirmation, when the doc's route isn't `/shape`) |
| work | `/review` | `/build`, `/next` (on confirmation, when the branch's route isn't `/build`) |
| delivery | `/review --delivery` | `/ship`, `/next` (on confirmation) |

## Specialists

These are the agents shipping today, each keeping the lane and rubric it owns now. One
specialist serves both cadences: a diff-scoped lane inside a `/review` episode, and a
whole-project duty under `/health` — which dispatches gauntlet's posture judges for it
(#334 S3); the local `review-*` files stay until #334 S4 retires them. The title is keyed
to the agent filename here so a title/agent pair cannot drift.

| Specialist | Episode lane (diff-scoped) | Periodic duty |
|---|---|---|
| Security Engineer | `security-auditor` | `review-security-health` |
| Architect | `architecture-auditor` | `review-architecture` |
| Ops Engineer | `operability-auditor`, `infra-auditor` | — |
| QA Engineer | `test-auditor` | — |
| Code Reviewer | `code-auditor` | `review-codebase-health` |
| Tech Writer | `doc-auditor` | `review-readme` |
| Frontend Engineer | `frontend-reviewer`, `ux-reviewer`, `accessibility-auditor` | `review-interface-health` |
| Dependency Steward | `dependency-auditor` | — |
| Prompt Engineer | `prompt-auditor` | `review-prompt-health` |
| Product Analyst | `product-reviewer` | `review-product-health` |
| Pre-mortem Verifier | `premortem-auditor` | — |
| Outcome Analyst | — | `review-outcomes` |

A `—` in the periodic column means no whole-project twin exists yet (see the hiring
ruling below).

## Rulings this charter carries

The design doc these tables came from was branch-local and disposable, per CLAUDE.md's
"Where a design record lives" rule; it was removed at closeout. Its durable half is here,
plus the failure modes in `docs/studious/premortems/persona-restructure.md`. What it
ratified, in one line each:

- **The flow is scale-invariant.** A bet's scope may be one story, a list of stories, or a
  whole milestone. The entry (`/bet`, where scope, stories, and appetite are approved), the
  exit (`/ship`), and every door between are the same at every scale. Scope changes how
  many stories a bet contains and how much runs dispatched versus supervised — never which
  doors exist.
- **A persona is a charter plus durable records, never a resident agent.** See the tripwire
  paragraph at the top of this file.
- **The doors are named for stages, not mechanisms** — the vocabulary kanban, Scrum, XP, and
  Shape Up already teach. Borrowing the names adopts no ceremony; PRODUCT.md's "no sprint
  ceremony" tripwire stands.
- **Appetite is the Product Owner's, set at `/bet`.** A budget, not an estimate, and the
  user's number rather than a model's. Mechanics live in `reference/epic-pricing.md`.
- **Growing the team means hiring a specialist** — a lane plus its periodic twin, behind
  demonstrated need, the way the Ops Engineer entered (infra first, then operability).

**One deviation from that design.** The design ratified deprecation shims for one
minor-version window; the restructure shipped a hard cut instead — no shim files, and
`/doctor` detects retired door names in a consuming project and proposes the rewire.
Reasoning: the shim rationale rested on marketplace muscle memory for an installer base
of one, against fifteen files carrying a deferred deletion chore. Reversing it is
additive — adding shims later costs nothing that removing them now didn't.

## Consumers that must stay in sync

Update this file first when a door changes, then these:

- `scripts/check_gate_independence.py` — derives its guarded surface and its producer-name
  list from the Doors table. No edit needed for a rename; it reads this file.
- `tests/python/test_persona_charter.py` — asserts every door listed here has its command
  file, every judge door lands on the guarded surface, and every agent named in the
  Specialists table exists.
- `README.md`'s command table, `PRODUCT.md`'s critical journeys, and `DESIGN.md`'s
  interface-contract section — human-facing prose, derived by hand from this table.
- `commands/doctor.md` — reads the Absorbed column to detect a consuming project whose
  `CLAUDE.md` still names a retired door.
