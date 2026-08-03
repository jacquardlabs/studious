# Routing telemetry format — dispatch identity and gate-time outcome labels

Two record kinds, one append-only store, one join key. A **dispatch** record names who
was sent to do a piece of review work and under which model; an **outcome** record names
the closed-enum verdict that work produced. Joined, they answer the only question the
routing initiative has: does this model, on this kind of step, tend to pass the gate.

Both live in `.studious/telemetry/<branch-slug>.jsonl` — local, gitignored, one JSON
object per line, same store shape and root-anchoring as `.studious/evidence/`. Written
by `bin/gate-ledger` (`telemetry-dispatch`, and `record`'s own outcome side effect);
`hooks/dispatch-telemetry.sh` is a caller of the first, never a second writer.

## Scope: a pure writer, no reader yet

Like `reference/events-format.md`'s store, this one ships with no read verb and no
consumer in this plugin. Nothing in the gate flow branches on it — a missing, empty, or
malformed telemetry file changes no verdict anywhere. It exists so the routing work has
a left side to join against, and so the two write paths below don't drift from each
other silently. This file, not either implementation, is the contract.

## Envelope

```json
{"at":"2026-08-02T14:02:03Z","kind":"dispatch","capturer":"hook", ...}
```

| Field | Notes |
|-------|-------|
| `at` | UTC `%Y-%m-%dT%H:%M:%SZ`, stamped by the writer, never a caller-supplied flag. Physical line order is not guaranteed under concurrent writers (the audit fan-out is 11+ simultaneous dispatches) — sort by `at`. |
| `kind` | `dispatch` or `outcome`. Determines which payload fields follow. |
| `capturer` | Which write path produced the line: `hook` (`hooks/dispatch-telemetry.sh` observing a `Task` dispatch), `driver` (a dispatch prompt built by `workflows/epic-driver.js` self-reporting its own driver-computed identity), or `ledger` (an outcome line, written by `record` itself). `ledger` is hardcoded by `record`; on dispatch lines the value is `--capturer`, validated against the closed `hook\|driver` set but claimed by the caller — provenance there is honest labeling, not proof. |

No `schemaVersion` per line, matching `reference/evidence-format.md` and
`reference/events-format.md`: each line is a flat, self-describing object, not part of
one versioned document.

**Envelope keys are camelCase-free and payload keys are `snake_case`** — deliberately
unlike the rest of this repo's JSON, and worth stating so it doesn't read as drift. The
eight identity fields below are fixed by the cross-surface event shape jacquardlabs/
studious#186 defines for build-task dispatch. A downstream replay or routing tool joins
gate dispatches and build dispatches in one table; making it translate field names per
surface is exactly the undocumented format agreement CLAUDE.md's repo-boundary rule
warns about. The envelope keeps `at`/`kind` because that is this repo's own append-only
convention and no cross-surface consumer reads them.

## `kind: "dispatch"`

```json
{"at":"2026-08-02T14:02:03Z","kind":"dispatch","capturer":"hook","run_id":"3f9c…","step_id":"toolu_01ABC…","parent_step_id":"","task_id":"feat/telemetry","skill":"gate-audit","role":"security-auditor","model":"opus","effort":"high","routing_reason":"static","features":{"prompt_bytes":8214}}
```

| Field | Source | Notes |
|-------|--------|-------|
| `run_id` | `--run-id` | The session or driver run this dispatch belongs to. The hook passes the harness `session_id`; the driver passes `epic:<slug>:<start-epoch>`. |
| `step_id` | `--step-id` | Unique within the run. The hook passes `tool_use_id`; the driver passes `<story>:<gate>:r<round>:<lane>`. |
| `parent_step_id` | `--parent-step-id` | The step this dispatch hangs off. The driver passes the gate step (`<branch-slug>:<gate>`), which is exactly what an outcome line's `step_id` defaults to — that is the join. The hook passes the enclosing subagent's `agent_id`, or `""` at top level. |
| `task_id` | `--task-id`, defaulting to the current branch name | The unit of work under review. |
| `skill` | `--skill` | The dispatch surface: `gate-audit`, `gate-acceptance`, `deep-review`, `review-outcomes`. |
| `role` | `--role` | The agent's own `name` (`security-auditor`), never the `studious:`-qualified dispatch string. |
| `model` | `--model`, else resolved from `agents/<role>.md`'s frontmatter | `inherit` is recorded verbatim when that is what the agent declares — that is live evidence for #136, not a gap to paper over. Empty only when neither a flag nor an agent file supplied one. |
| `effort` | `--effort`, same fallback | The other half of the cost dial (CLAUDE.md pins `model` and `effort` independently). |
| `routing_reason` | `--routing-reason` | Closed set: `static` (a fixed roster), `override` (something displaced the static roster — a narrowed re-audit round is `override`), `classifier:v<digits>` (a literal `v` followed by digits only), or `ab:<arm>` (`<arm>` is one non-empty token with no whitespace or control characters). Rejected otherwise. |
| `features` | zero or more `--feature <name>=<value>` | Classifier features cheaply available at dispatch time. Values coerce to number or boolean when they parse as one, else stay strings. Names align with #186 where the concept carries over (`input_bytes`, `files_touched`, `load_bearing`); gate-specific names used today are `prompt_bytes` (hook) and `round`, `narrowed`, `lane_count` (driver). The set is open by design — a new feature is a new `--feature`, never a schema change. |

## `kind: "outcome"` — the gate-time label

```json
{"at":"2026-08-02T14:19:40Z","kind":"outcome","capturer":"ledger","run_id":"3f9c…","step_id":"feat-telemetry:audit","task_id":"feat/telemetry","gate":"audit","verdict":"PASS","sha":"d4e5f6a"}
```

Written by `record` as a side effect of every verdict it already persists — one line per
`record` call, no new call site, no prompt asked to remember anything. `verdict` is the
closed-enum token `reference/gate-vocabulary.md` defines; this store never invents,
normalizes, or re-spells it.

| Field | Source |
|-------|--------|
| `run_id` | `--run-id`, else the run last seen on this branch (see below), else `""`. |
| `step_id` | `--step-id`, else `<branch-slug>:<gate>` — the gate step every dispatch line's `parent_step_id` already points at. |
| `task_id` | The branch name. |
| `gate`, `verdict`, `sha` | `record`'s own already-recorded values, verbatim. |

This is a **gate-time** label, available at the moment of verdict. It is not #65's
post-ship signal (production bugs, reverts, weeks later) and must not be merged with it:
one measures whether the review passed, the other whether the shipped thing held up.

### How a verdict finds its run without a prompt carrying an id

`telemetry-dispatch` writes the run it was given to `.studious/telemetry/<branch-slug>.run`,
a one-line file. `record` reads it. So an interactive `/gate-audit` session — which
cannot see its own `session_id` from inside a prompt — still produces outcome lines
joinable to the dispatch lines the hook wrote minutes earlier, with no instruction added
to any command and nothing for a model to forget. Code owns this bookkeeping entirely.

The attribution rule this implies, stated plainly: **a verdict is attributed to the last
run that dispatched a review on that branch.** Two sessions reviewing one branch
concurrently would mis-attribute; that is accepted, not overlooked. Nothing branches on
this data, and the alternative is a run id threaded through four prompt strings that a
model would have to reproduce verbatim.

## The join

Primary key: `(run_id, parent_step_id)` on a dispatch line matches `(run_id, step_id)`
on an outcome line. Rounds are distinguished by ordering outcome lines by `at` and
matching the Nth outcome to the dispatch lines carrying `features.round == N`.

Degraded key, for the hook path: the hook cannot see which round it is in or which
command dispatched it, so its `parent_step_id` is the enclosing `agent_id` (usually
`""`), not the gate step. A joiner falls back to `(run_id, task_id, skill)` and
attributes every dispatch line in that run to that run's outcome lines for the same
branch. Coarser, and it is the honest limit of what a `PreToolUse` hook can know.

## What each surface emits

**The interactive commands emit nothing themselves.** `/gate-audit`, `/gate-acceptance`,
and `/deep-review` are prose read by a human-invoked session; adding a per-lane ledger
call to their fan-out would spend 11–13 extra Bash round-trips per round to record what
the hook already sees for free. `hooks/dispatch-telemetry.sh` fires on the `Task` tool
and writes one dispatch line per lane. The commands carry a pointer to this file and
nothing else — the schema lives here, in one place.

**The driver emits explicitly**, because it is code and knows things no hook can
observe: which round this is, whether the roster was narrowed, and which lanes were
routed out. `workflows/epic-driver.js` stamps the ledger call into each auditor's own
dispatch prompt with those values already computed.

Both paths therefore write the same store, and a dispatch the driver stamped must not
also be recorded by the hook. The suppression is mechanical: a driver-stamped prompt
carries the literal sentinel `STUDIOUS-TELEMETRY-SELF-REPORT`, and the hook exits
silently when it sees that string in `tool_input.prompt`. The token is deliberately
unlikely to occur in ordinary prose — matching on `telemetry-dispatch` would suppress on
any prompt that happened to quote this document.

## What the hook can and cannot see

Verified against code.claude.com/docs/en/hooks (Common input fields, PreToolUse), not
assumed: every hook receives `session_id`, `transcript_path`, `cwd`, `permission_mode`,
and `hook_event_name`; `PreToolUse` adds `tool_name`, `tool_input`, and `tool_use_id`;
`agent_id` and `agent_type` are present only when the hook fires inside a subagent call;
and `PreToolUse` matchers match the tool name, so `"Task"` is a valid matcher.

**Assumed, not verified:** the documentation does not enumerate the `Task` tool's own
`tool_input` fields. The hook reads `subagent_type` and `prompt` from it and exits
silently — no record, no error — when `subagent_type` is absent or empty, so a wrong
assumption here degrades to zero telemetry rather than to wrong telemetry. The `Task`
input carries no model field of any kind, verified or otherwise, which is why `model`
resolves from `agents/<role>.md` inside `telemetry-dispatch` instead.

The hook deliberately does **not** require the branch to be armed the way
`hooks/evidence-capture.sh` does. `/deep-review` runs on `main`, against no story, with
no work file — an armed check would silence exactly half of what this store exists to
record. The dispatch of a named Studious reviewer is itself the signal; the roster table
in the hook is the whole filter.

### `skill` on the hook path

The hook derives `skill` from the role by pattern — `review-*` is `/deep-review`'s,
`*-auditor`/`*-reviewer` is `/gate-audit`'s — plus the carve-outs the patterns cannot
carry: `product-reviewer` and `premortem-auditor` belong to `/gate-acceptance`;
`review-outcomes` matches `review-*` but is dispatched by its own `/review-outcomes`
command, which runs outside the `/deep-review` sweep, so it maps to `review-outcomes`
before the pattern is consulted; and `code-auditor` is genuinely ambiguous (it serves
both `/gate-audit`'s lane 2 and `/deep-review`'s idiom-feedback step), so its lines
carry `skill: ""` rather than a confident guess and a joiner resolves them from the
run's other lines. Every carve-out is tested before the patterns, since all four names
match one.

The allow-list is `agents/<role>.md` existing: a role that matches no pattern, or matches
one but names no shipped agent, produces no record at all — same conservative posture as
the evidence hook's token list. Deliberately a pattern and not a roster copy:
`workflows/epic-driver.js`'s `AUDITORS` comment already names three hand-maintained
copies of the auditor list as a standing drift risk (#271), and a fourth would silently
drop whichever lane ships next.

## Failure behavior

Every write here is best-effort and secondary, exactly like `append_event()`:

- `record`'s outcome append runs only after its own primary snapshot write succeeded,
  signals on stderr if it fails, and always leaves `record`'s exit code untouched. A
  full disk cannot turn a recorded PASS into a failed gate command.
- `telemetry-dispatch` returns 0 when `jq` or `git` is unavailable, after saying so on
  stderr — the same degradation every other verb in `bin/gate-ledger` uses.
- The hook is silent on every path: no stdout, no permission decision, never blocks.

## No retention or pruning

`cmd_gc` prunes per-branch gate and work files whose branch no longer exists; this store
adds no rule of its own, matching `reference/events-format.md`. Telemetry outlives the
branch it describes, which is the point — a routing comparison reads runs that finished
long ago.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh` asserts `telemetry-dispatch`'s field shape, its validation,
  the agent-frontmatter model fallback, and `record`'s outcome side effect.
- `tests/test_dispatch_telemetry.sh` asserts the hook's roster filter, skill mapping,
  sentinel suppression, and defensive exits.
- `workflows/epic-driver.js`'s audit fan-out builds the driver-side call; changing the
  flag set means changing that prompt builder in the same commit.
