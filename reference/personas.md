# Persona charter — the doors, who owns them, and what each may do

Canonical source for Studious's command surface and the lane rule that keeps it honest.
This file is **data**: the tables below are parsed by `scripts/check_gate_independence.py`
to derive the guarded surface, and by `tests/python/test_persona_charter.py` to assert the
prose surfaces agree. Change a door here first, then change the door.

**The test is residency, not vocabulary.** A persona is a charter plus durable records —
never a resident agent. Every agent in `agents/` is dispatched fresh, judges once, and
exits; naming the roles below does not create standing ones. Read this paragraph before
concluding the roster describes anything that stays running, because nothing does.

## Doors

Nine doors, seven of them day-to-day. The `Class` column is load-bearing: it is what
`check_gate_independence.py` reads to decide which files it guards and which command
names count as producer invocations.

A door is backed by a `commands/*.md` file or a `skills/*/SKILL.md` file — both are
invokable slash commands, and which one backs a door is an implementation detail, not a
class distinction. The `Backed by` column is the authority either way.

| Door | Persona | Class | Backed by | Absorbed |
|---|---|---|---|---|
| `/bet` | Product Owner | judge | `commands/bet.md` | gate-should-we-build, backlog-priorities |
| `/shape` | Designer | producer | `skills/shape/SKILL.md` | design |
| `/review` | Design Reviewer, Reviewer | judge | `commands/review.md` | gate-design-review, gate-audit, gate-acceptance |
| `/build` | Builder | producer | `skills/build/SKILL.md` | plan, build |
| `/ship` | Shipper | producer | `skills/ship/SKILL.md` | finish, handback |
| `/next` | Navigator, Orchestrator | navigator | `commands/next.md` | work-on, work-through, coach |
| `/retro` | Health Officer | periodic | `commands/retro.md` | deep-review, backlog-hygiene, review-outcomes |
| `/setup` | — | infra | `commands/setup.md` | studious-init, extract-product-context, extract-design-system |
| `/doctor` | — | infra | `commands/doctor.md` | studious-doctor |

### What each class may do

- **judge** — records verdicts. May never invoke a producer door or require a producer's
  private artifact, because a gate judges the work and never who produced it. This is the
  rule `scripts/check_gate_independence.py` enforces; `reference/worker-contract.md` is the
  executor-agnostic contract a judge may rely on instead.
- **producer** — writes and commits code, docs, and evidence. May name other producers and
  may *convene* a judge (`/ship` convenes the delivery episode), but may never write a
  verdict. Convening is not judging.
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
| design | `/review` | `/next` (on confirmation) |
| work | `/review` | `/next` (on confirmation) |
| delivery | `/review --delivery` | `/ship`, `/next` (on confirmation) |

## Specialists

The specialist tier already exists — these are the agents shipping today, each keeping
exactly the lane and rubric it owns now. One specialist serves both cadences: a
diff-scoped lane inside a `/review` episode, and a whole-project duty under `/retro`.
The title is keyed to the agent filename here so a title/agent pair cannot drift.

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

A `—` in the periodic column means that specialist has no whole-project twin today.
Adding one is a hire: a lane plus its periodic duty, behind demonstrated need, the way
the Ops Engineer entered (infra first, then operability).

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
