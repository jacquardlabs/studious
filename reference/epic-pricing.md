# Epic pricing — lookup data

`/work-through`'s plan piece stops once, for the user to approve a story plan. This
file is what turns that stop into a *priced* one: how to estimate what the approved
plan will cost before it runs, and how to propose the appetite the driver then
enforces as a ceiling. It is lookup data read at plan approval — nothing in
`workflows/epic-driver.js` reads it, and nothing here is recorded except the two
approved numbers.

**Why the number belongs at approval.** Two dogfooded runs of the same command
against the same repo ([#144](https://github.com/jacquardlabs/studious/issues/144)):

| Run | Invocations | Agents | Tokens | Wall clock | Landed |
|---|---|---|---|---|---|
| M3 (2026-07-17) | 1 | 74 | 3.83M | 93 min | 5/5 |
| M11 (2026-07-26/27) | 7 | ~311 | ~22M | 16.6 h | 5/11 |

Nobody chose to spend 22M tokens. The run had no ceiling to reach, because the price
was never visible at a moment anyone could act on it. Approval is that moment: the
user approves scope and spend together, or trims the plan until the number is one
they like.

## The estimate is in tokens; dollars are display only

Tokens are the unit the ceiling is enforced in — `workflows/epic-driver.js` reads the
Workflow `budget` primitive, whose `remaining()` is tokens — and the unit the measured
history below is recorded in. Convert to dollars for the human reading the plan if it
helps them decide, but **the number recorded as the appetite is always tokens.** A
dollar figure recorded as the appetite would be a rate table stored in a ledger, going
stale silently against every price change.

## Where the multiplicand comes from — a two-rung ladder

Take the highest rung that has data, and say which rung you used.

1. **Measured, from this project's own history.** The store is
   `.studious/telemetry/<branch-slug>.jsonl` (`reference/telemetry-format.md`) joined
   on `task_id` — a story's branch — plus the run reports of prior driver invocations
   and any `cctx` session costs the user has. This is the rung
   [#296](https://github.com/jacquardlabs/studious/issues/296) asks for, and it is
   partial today: the telemetry store records *which* dispatches went out (one
   `dispatch` line per review agent, with model and effort) but not what each one
   spent, so a measured estimate is a measured **dispatch count** priced with the
   floor below, not a measured token total. Say that when you use it.
2. **The pinned floor.** No usable history — a first epic, a fresh checkout, a project
   whose telemetry predates joinable identity. Use the per-phase table below and label
   the result a floor estimate, provisional.

Never estimate from a model's own guess at what it will spend. The measured position
in the literature is that models cannot predict their own token usage (correlation
≤ 0.39, arXiv:2604.22750) and that identical tasks vary up to 30x — which is also why
the appetite proposed below is a p99, not a mean.

## The pinned floor, per phase, per story

Apportioned from M3's measured 3.83M tokens across 5 stories (0.77M/story) over the
phases each story ran. These are **floor** numbers: the cheapest a phase plausibly
runs, with no fix cycle.

| Phase | Floor (tokens) | What it buys |
|---|---|---|
| `design` | 0.15M | one worker drafting the doc against `reference/worker-contract.md` |
| `design-review` | 0.10M | one opus gate agent against `reference/design-doc-contract.md` |
| `build` | 0.25M | one worker, the largest single dispatch in a story |
| `audit` | 0.20M | the routed audit fan-out (up to 11 lanes) plus its compile step |
| `acceptance` | 0.10M | scope probe, product review, walkthrough, premortem lane, compile |
| merge + bookkeeping | 0.02M | haiku merge, verify read-back, park/ready records |

Plus **0.30M once per epic** for the finale — the cross-story audit fan-out,
`/gate-acceptance` against the epic goal, and the pre-mortem verification.

**Fix cycles are the range, not a rounding error.** `workflows/epic-driver.js` allows
up to `MAX_FIX_CYCLES` (2) retries per gate, and each retry costs a fixer dispatch plus
a fresh gate round. Price the plan as a range: the floor above with no fix cycles, and
a ceiling of roughly **2x** the `audit` + `acceptance` lines with every gate taking its
full allowance.

Rates, for the dollar figure only — **verified 2026-08-02**, first-party API list
price per million tokens. A stale row here is a display bug, never a ceiling bug,
because the ceiling is denominated in tokens:

| Model | Input $/MTok | Output $/MTok |
|---|---|---|
| Opus (`claude-opus-5`) | $5.00 | $25.00 |
| Sonnet (`claude-sonnet-5`) | $3.00 | $15.00 |
| Haiku (`claude-haiku-4-5`) | $1.00 | $5.00 |

Which lane runs on which tier is the gate commands' and agents' own `model`
frontmatter, not a fact this file duplicates.

## What to propose as the appetite

Two numbers, both approved at the same stop, both recorded on the epic.

**Tokens — propose the p99 of the measured distribution**, or, on the floor rung, the
top of the range computed above. Anthropic's task-budget guidance is explicit that
budgets should be sized from measured distributions starting at p99, and that a budget
set too small does not fail loudly — the work quietly scopes down instead, which reads
as a weaker result rather than as a ceiling being hit. **Say that out loud whenever the
user proposes a tighter number than the estimate**: a tight appetite is a legitimate
choice, and it is a choice to accept a degraded result, not a smaller one.

**Open episodes — propose the epic's concurrency cap, and let the user tighten it.**
This is the second appetite number
([#297](https://github.com/jacquardlabs/studious/issues/297)): the maximum stories that
may be awaiting judgment or human action at once. Every practitioner report converges
on 1–4 as the effective concurrency where a human is in the loop, and M11 demonstrated
the failure mode from the other side — 22M tokens, 7 invocations, and one person
absorbing 21 fix-round verdicts. Token headroom does not bind at ship time; review
bandwidth does. A story parked by the plan as `story-supervised` counts against this
number exactly like one this run parked on a gate verdict — both are work the person
has to come back to.

## Show the estimate the way the profile was shown

The gate profile is presented with the inputs that produced it
(`reference/epic-plan-contract.md`), and the price follows the same rule: show the
per-story lines, the rung the multiplicand came from, and the range — never a bare
total. A user cannot trim a plan toward a number they like if the number arrives
without its parts.

## Consumers that must stay in sync

- `commands/work-through.md` — the only reader. Its plan piece computes the estimate
  here and records the approved numbers via `gate-ledger epic-set --appetite-tokens`
  / `--appetite-episodes`.
- `bin/gate-ledger` — stores them on the epic (`appetite.tokens`,
  `appetite.openEpisodes`) and computes the zero-landed stop-loss from the `runs`
  history `epic-run-log` appends.
- `workflows/epic-driver.js` — enforces both at runtime and prices nothing. It reads
  `epic.appetite` and the Workflow `budget` primitive; it holds undispatched stories
  when either ceiling is reached. If it ever computed a rate, that would be a second
  source of truth for cost.
- `reference/telemetry-format.md` — the measured rung's store. When a per-dispatch
  token count lands there, rung 1 stops being a dispatch count priced with the floor,
  and this file's ladder is what has to say so.
