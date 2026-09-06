# Routing telemetry format — dispatch identity and gate-time outcome labels

Two record kinds, one append-only store, one join key. A **dispatch** record names who
was sent to do a piece of review work and under which model; an **outcome** record names
the closed-enum verdict that work produced. Joined: does this model, on this kind of
step, tend to pass the gate.

Both live in `.studious/telemetry/<branch-slug>.jsonl` — local, gitignored, one JSON
object per line, same store shape and root-anchoring as `.studious/evidence/`. Written
by `bin/gate-ledger` (`telemetry-dispatch`, and `record`'s own outcome side effect);
`hooks/dispatch-telemetry.sh` is a caller of the first, never a second writer.

## Scope: one reader, and nothing branches on it

This store ships with no read verb; its one consumer in this plugin is `/retro`'s
`scripts/retro-stats` (#330), which reads the files directly under this contract and renders
dispatch counts per story and verdicts per branch for the retrospective's cycle numbers. A
missing, empty, or malformed telemetry file changes no verdict anywhere — the reader reports
a gap, never a zero. The store exists so the routing work has a left side to join against,
and so the two write paths below don't drift from each other. This file, not either
implementation, is the contract.

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
unlike the rest of this repo's JSON. The eight identity fields below are fixed by the
cross-surface event shape jacquardlabs/studious#186 defines for build-task dispatch, so a
downstream tool joining gate and build dispatches in one table need not translate field
names per surface (the undocumented-format-agreement risk CLAUDE.md's repo-boundary rule
warns about). The envelope keeps `at`/`kind` as this repo's own append-only convention;
no cross-surface consumer reads them.

## `kind: "dispatch"`

```json
{"at":"2026-08-02T14:02:03Z","kind":"dispatch","capturer":"hook","run_id":"3f9c…","step_id":"toolu_01ABC…","parent_step_id":"","task_id":"feat/telemetry","skill":"gate-audit","role":"security-auditor","fleet":"studious","model":"opus","effort":"high","routing_reason":"static","features":{"prompt_bytes":8214}}
```

| Field | Source | Notes |
|-------|--------|-------|
| `run_id` | `--run-id` | The session or driver run this dispatch belongs to. The hook passes the harness `session_id`; the driver passes `epic:<slug>:<start-epoch>`. |
| `step_id` | `--step-id` | Unique within the run. The hook passes `tool_use_id`; the driver passes `<story>:<gate>:r<round>:<lane>`. |
| `parent_step_id` | `--parent-step-id` | The step this dispatch hangs off. The driver passes the gate step (`<branch-slug>:<gate>`), which is exactly what an outcome line's `step_id` defaults to — that is the join. The hook passes the enclosing subagent's `agent_id`, or `""` at top level. |
| `task_id` | `--task-id`, defaulting to the current branch name | The unit of work under review. |
| `skill` | `--skill` | The dispatch surface: `gate-audit`, `gate-acceptance`, `health`, `review-outcomes`, or `deep-review` for a local `review-*` agent dispatched by hand (the retired `/retro` sweep's key, kept until #334 S4 deletes those files). |
| `role` | `--role` | The agent's own `name` (`security-auditor`, `codebase-posture-auditor`), never the `studious:`- or `gauntlet:`-qualified dispatch string — `telemetry-dispatch` refuses a colon. `fleet` says which plugin the name belongs to. |
| `fleet` | `--fleet` | `studious` or `gauntlet`: whose agent `role` names. Optional and caller-claimed like `capturer`; the hook always sets it, the driver sets nothing until #334 S2, so `""` means unstated. A same-named lane in both fleets (`security-auditor`) is two different judges with two different pins — this is the field that keeps them apart. Added as an optional field, which is not a bump: no per-line schema version exists to bump (above), and a reader that ignores it reads every line as before. |
| `model` | `--model`, else resolved from `agents/<role>.md`'s frontmatter unless `fleet` is `gauntlet` (an unstated fleet still resolves) | `inherit` is recorded verbatim when that is what the agent declares — that is live evidence for #136, not a gap to paper over. Empty is the normal case for a `gauntlet` role — its pin lives in gauntlet's own plugin, which this one never reads, and a same-named local agent is not consulted — so the #136 `inherit` evidence stream ends for each lane the moment it migrates (gauntlet's pins are that issue's fix). Also empty for a local role with no agent file. |
| `effort` | `--effort`, same fallback | The other half of the cost dial (CLAUDE.md pins `model` and `effort` independently). |
| `routing_reason` | `--routing-reason` | Closed set: `static` (a fixed roster), `override` (something displaced the static roster — a narrowed re-audit round is `override`), `classifier:v<digits>` (a literal `v` followed by digits only), or `ab:<arm>` (`<arm>` is one non-empty token with no whitespace or control characters). Rejected otherwise. |
| `features` | zero or more `--feature <name>=<value>` | Classifier features cheaply available at dispatch time. Values coerce to number or boolean when they parse as one, else stay strings. Names align with #186 where the concept carries over (`input_bytes`, `files_touched`, `load_bearing`); gate-specific names used today are `prompt_bytes` (hook) and `round`, `narrowed`, `lane_count` (driver). The set is open by design — a new feature is a new `--feature`, never a schema change. |

## `kind: "outcome"` — the gate-time label

```json
{"at":"2026-08-02T14:19:40Z","kind":"outcome","capturer":"ledger","run_id":"3f9c…","step_id":"feat-telemetry:audit","task_id":"feat/telemetry","gate":"audit","verdict":"PASS","sha":"d4e5f6a"}
```

Written by `record` as a side effect of every verdict it already persists — one line per
`record` call, no new call site. `verdict` is the closed-enum token
`reference/gate-vocabulary.md` defines; this store never invents, normalizes, or
re-spells it.

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
a one-line file. `record` reads it, so an interactive `/review` session — which cannot
see its own `session_id` from inside a prompt — still produces outcome lines joinable to
the dispatch lines the hook wrote minutes earlier, with no instruction added to any
command. Code owns this bookkeeping entirely.

**A verdict is attributed to the last run that dispatched a review on that branch.** Two
sessions reviewing one branch concurrently would mis-attribute; that is accepted, not
overlooked. Nothing branches on this data, and the alternative is a run id threaded
through four prompt strings that a model would have to reproduce verbatim.

## The join

Primary key: `(run_id, parent_step_id)` on a dispatch line matches `(run_id, step_id)`
on an outcome line. Rounds are distinguished by ordering outcome lines by `at` and
matching the Nth outcome to the dispatch lines carrying `features.round == N`.

Degraded key, for the hook path: the hook cannot see which round it is in or which
command dispatched it, so its `parent_step_id` is the enclosing `agent_id` (usually
`""`), not the gate step. A joiner falls back to `(run_id, task_id, skill)` and
attributes every dispatch line in that run to that run's outcome lines for the same
branch — the honest limit of what a `PreToolUse` hook can know.

## What each surface emits

**The interactive commands emit nothing themselves.** `/review`, `/review --delivery`,
and `/health` are prose read by a human-invoked session; a per-lane ledger call in their
fan-out would spend 11–13 extra Bash round-trips per round recording what the hook
already sees for free. `hooks/dispatch-telemetry.sh` fires on the `Task` tool and writes
one dispatch line per lane; the commands carry a pointer to this file, nothing else.

**The driver emits explicitly**, because it is code and knows things no hook can
observe: which round this is, whether the roster was narrowed, which lanes were routed
out. `workflows/epic-driver.js` stamps the ledger call into each auditor's own dispatch
prompt with those values already computed.

A dispatch the driver stamped must not also be recorded by the hook. Suppression is
mechanical: a driver-stamped prompt carries the literal sentinel
`STUDIOUS-TELEMETRY-SELF-REPORT`, and the hook exits silently when it sees that string in
`tool_input.prompt`. Matching on `telemetry-dispatch` instead would suppress any prompt
that happened to quote this document.

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
resolves from `agents/<role>.md` inside `telemetry-dispatch` unless `fleet` is
`gauntlet`, in which case it stays empty.

The hook deliberately does **not** require the branch to be armed the way
`hooks/evidence-capture.sh` does. `/health` runs on `main`, against no story, with no work
file — an armed check would silence half of what this store exists to record. The
dispatch of a named reviewer is itself the signal; the roster table in the hook is the
whole filter.

### `skill` on the hook path

The hook derives `skill` from the role by pattern — `*-posture-*` is `/health`'s
(gauntlet's posture judges, #334 S3), `review-*` is the retired local sweep's
`deep-review`, `*-auditor`/`*-reviewer` is `/review`'s — plus carve-outs the patterns
can't carry: `product-reviewer` and `premortem-auditor` belong to `/review --delivery`;
`review-outcomes` matches `review-*` but is dispatched by `/retro`, so it's mapped before
the pattern is consulted; `code-auditor` served both `/review`'s lane 2 and the old
idiom-feedback step, genuinely ambiguous, so its lines carry `skill: ""` and a joiner
resolves them from the run's other lines. Every carve-out is tested before the patterns,
since all four names match one. Both fleets map alike: gauntlet's acceptance lanes carry
the same names as the local ones.

The allow-list is `agents/<role>.md` existing for a local role, and the `gauntlet:` prefix
itself for one of gauntlet's judges — its roster is gauntlet's charter, not a file here,
and `model`/`effort` stay empty for the same reason. The two rules never blend: a
`gauntlet:` dispatch never consults a same-named local file, and a local dispatch never
records under the wrong fleet. A role that matches no pattern, or matches one but names
no shipped agent, produces no record — same conservative posture as the evidence hook's
token list. Deliberately a pattern and not a roster copy:
`workflows/epic-driver.js`'s `AUDITORS` comment already names three hand-maintained
copies of the auditor list as a standing drift risk (#271); a fourth would silently drop
whichever lane ships next.

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
branch it describes — a routing comparison reads runs that finished long ago.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh` asserts `telemetry-dispatch`'s field shape, its validation,
  the agent-frontmatter model fallback and its `fleet` gate, and `record`'s outcome side
  effect.
- `tests/test_dispatch_telemetry.sh` asserts the hook's two-fleet allow-list, skill
  mapping, sentinel suppression, and defensive exits.
- `workflows/epic-driver.js`'s audit fan-out builds the driver-side call; changing the
  flag set means changing that prompt builder in the same commit. `--fleet` is the one
  standing exception: optional, and the driver adopts it at #334 S2 when its dispatches
  move — not drift.
- `scripts/retro-stats` reads `kind`, `task_id`, `model`, and `skill` off dispatch lines and
  `task_id` off outcome lines; renaming any of those means changing its cost table.
