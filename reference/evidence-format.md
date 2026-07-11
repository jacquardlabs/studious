# Evidence record format — the harness-captured verification log

`hooks/evidence-capture.sh` and `bin/gate-ledger`'s `evidence-append` verb write one
JSON object per line to `.studious/evidence/<branch-slug>.jsonl` for every verification
command run while a story is armed. This file pins the exact shape so drift from what
the hook actually writes is a visible diff against this doc, not a silent surprise —
and pins how far this story goes into winnow's evidence format, so a later story
extending it has one place to check against instead of re-deriving scope from the
amendment itself.

## Scope: winnow Amendment 006's early footprint only

Source: `docs/amendments/006-evidence-bundles.md` in the sibling `winnow` repo (itself
"Proposed — pending owner adoption" there, not a frozen spec), "Early footprint (cheap
now, structural later)" section. This story implements exactly its two rules and
nothing past them:

1. **Capturer provenance**, recorded on every record — `capturer: "hook"` in v0, a
   constant, because Studious has no persistent daemon process the way winnow's design
   assumes. Recording it now (as a constant) rather than waiting for a second capturer
   type to exist is the "cheap now" half of the rule.
2. **in-toto predicate-shaped test-result records** — every captured command (test,
   lint, typecheck, or build) maps onto in-toto's existing `test-result` predicate
   (`https://in-toto.io/attestation/test-result/v0.1`), not a second, studious-invented
   predicate type.

**Explicitly not built here** (Amendment 006's Phase 2, "workstream 7"): DSSE-signed
envelopes, sigstore keyless signing, driven-flow browser/CLI recordings, before/after
screenshot pairs, the standalone `exhibit render` path. A future story that adds any of
these should update this file's scope statement, not silently extend the shape below.

## Record shape

One compact JSON object per line, append-only, written by `cmd_evidence_append` in
`bin/gate-ledger` (never read-modify-write — see that function's comment for why an
append-only log doesn't need `json_update`'s rename dance).

```json
{
  "capturedAt": "2026-07-10T21:03:44Z",
  "capturer": "hook",
  "origin": "subagent",
  "agentType": "epic-driver:build-worker",
  "command": "uv run --no-project --with pytest pytest tests/python -v",
  "exitCode": 0,
  "outputDigest": "sha256:9f2c...",
  "predicateType": "https://in-toto.io/attestation/test-result/v0.1",
  "predicate": {
    "result": "PASSED",
    "configuration": [{ "name": "uv run --no-project --with pytest pytest tests/python -v" }]
  }
}
```

| Field | Source | Notes |
|-------|--------|-------|
| `capturedAt` | `now_iso()` inside `gate-ledger`, not a caller-supplied flag | UTC, `%Y-%m-%dT%H:%M:%SZ` |
| `capturer` | Hardcoded `"hook"` inside `cmd_evidence_append` | Not a flag — no caller can write a different capturer value. The field that makes capturer ≠ claimant checkable, per the amendment. |
| `origin` | `"subagent"` if the hook input's `agent_id` is present, else `"interactive"` | See "Open item: origin and /work-through's actual dispatch mechanism" below — this is a real, currently-unverified gap, not a settled fact. |
| `agentType` | Hook input's `agent_type`, when present | **Omitted entirely** (not `null`, not `""`) when absent — e.g. every `origin: "interactive"` record. |
| `command` | `tool_input.command`, verbatim | Also becomes `predicate.configuration[0].name` — one source, not duplicated independently. |
| `exitCode` | See "Resolved: PostToolUse vs PostToolUseFailure" below | `0` on the `PostToolUse` path; best-effort parsed (or a `1` sentinel) on the `PostToolUseFailure` path. |
| `outputDigest` | `sha256:<hex>` of a digest source that differs by event — see below | A digest, never raw output — Amendment 006 asks for a digest specifically, and raw command output is a plausible place for a secret to land (a token echoed by a failed auth check). |
| `predicateType` | Hardcoded, the in-toto test-result predicate URL | Not a flag. |
| `predicate.result` | `PASSED` if `exitCode == 0`, else `FAILED` | `WARNED` is unused in v0 — no generic, cross-tool way to detect "passed with warnings" without per-tool output parsing (Phase-2-shaped scope). |
| `predicate.configuration` | `[{ "name": "<command>" }]` | Fixed shape; not extended with flags/env in v0. |

`origin`/`agentType` are deliberately **not** nested inside `predicate` — everything
under `predicate`/`predicateType` mirrors winnow's shape exactly; `origin`/`agentType`
are studious's own dispatch-context fields, kept structurally separate so a future diff
against winnow's spec stays about winnow's fields only.

## Resolved: `PostToolUse` vs `PostToolUseFailure`

The design doc's own open question — "the exact `tool_response` field for Bash exit
status" — turned out to have no answer, because the premise was wrong. Verified against
`code.claude.com/docs/en/hooks` (the raw page content, not a summary): a Bash tool call
does **not** always fire `PostToolUse`. It fires exactly one of two distinct events, with
two distinct, non-overlapping input schemas:

- **`PostToolUse`** fires **only when the command exited zero**. `tool_response` has
  `stdout`, `stderr`, `interrupted`, and `isImage` — there is no exit-code field at all,
  because the event firing already means success. `exitCode` is hardcoded to `0` on
  this path, not read from a field.
- **`PostToolUseFailure`** fires when the command exited non-zero, or was interrupted.
  It carries a completely different shape: a human-readable `error` string (the
  documented example is literally a failing `npm test`: `"error": "Command exited with
  non-zero status code 1"`) plus `is_interrupt` — **no `stdout`/`stderr` at all**.

A hook registered on `PostToolUse` alone — the design doc's literal text — would never
see a failing verification run. That's not a mislabeled `PASSED`; it's silence: no
record at all for the exact case the story exists to make checkable. `hooks.json`
therefore wires **both** events to the same `hooks/evidence-capture.sh`, which branches
on `hook_event_name`.

Consequences of the split, both load-bearing:

- **`exitCode` on the failure path is best-effort.** `error`'s exact wording is an
  example in the docs, not a documented stable contract. The hook parses a trailing
  `[0-9]+` from it and falls back to a `1` sentinel when that doesn't match (e.g. an
  interrupted/timed-out command, where no numeric code exists to parse). `FAILED`
  itself never depends on the parse succeeding — only the exact number would be
  approximate in the fallback case.
- **`outputDigest`'s source differs by event**, because the failure path has no
  stdout/stderr to hash:
  - `PostToolUse`: `sha256:` of the compact JSON `{"stdout": ..., "stderr": ...}` (both
    streams, one deterministic serialization — not raw concatenation, which would need
    an arbitrary separator).
  - `PostToolUseFailure`: `sha256:` of the `error` string alone — the only content
    available on this event.

## Open item: `origin` and `/work-through`'s actual dispatch mechanism

`agent_id`/`agent_type` are documented as present "only when the hook fires inside a
subagent call" — i.e. a Claude Code Task-tool-dispatched subagent within one session.
That's confirmed from the docs, not guessed.

**Not confirmed:** whether `/work-through`'s primary dispatch path populates these the
same way. `workflows/epic-driver.js` dispatches workers through an `agent(...)` global
provided by the Workflow tool substrate (`commands/work-through.md`, "Run the driver
script (primary mode)") — a different, less-documented mechanism than the in-session
Task tool the fallback driver uses directly (`commands/work-through.md`'s "Fallback
driver" section explicitly dispatches via Task calls). Whether the Workflow tool's own
`agent()` primitive is, under the hood, a Task-tool subagent call (in which case
`agent_id` is populated and `origin` resolves to `"subagent"` correctly) or a separate
process/session entirely (in which case `agent_id` would never be present, and a real
dispatched worker's records would read `origin: "interactive"`) is not settled by
anything this story could verify: this worker has no Task tool of its own to dispatch a
real nested subagent and observe the hook input firsthand, and hot-reloading a live
session's own hook configuration to self-test was judged too invasive an action for a
story worker to take on its own runtime mid-task.

This is dogfood item zero's real remaining surface, not the mechanism-level question
(already resolved above: `PostToolUse`/`PostToolUseFailure` do fire for Bash calls made
inside a subagent, whichever dispatch path is in play). What this story's own tests
verify instead — deterministically, in CI, per `tests/test_evidence_capture.sh` — is
everything mechanically checkable without a live dispatch: that the hook correctly
resolves the armed check and writes to the **shared main-tree** evidence store when its
own process cwd is a **linked worktree** (mirroring a worker's actual cwd), and that
`origin` resolves to `"subagent"` given an `agent_id`-bearing payload shaped exactly per
the docs above. The one thing left unverified — does a real `/work-through` dispatch
populate `agent_id` — is exactly what issue #97's own dogfood plan (studyengine #210,
then #209) is the intended real-world validation loop for; a follow-up should update
this section, not silently leave it stale, once that run produces a real answer.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh`'s `evidence-append` tests assert the exact key set and
  ordering above — update both together.
- `tests/test_evidence_capture.sh` asserts the hook produces this shape end to end,
  including the `PostToolUse`/`PostToolUseFailure` split.
- `gate-ledger evidence-list` (added by `gates-cite-evidence`) is a plain passthrough of
  this shape, one line per record — it reshapes nothing written here.
  `commands/gate-audit.md` and `commands/gate-acceptance.md` stamp its raw output into
  `@agent-test-auditor`'s and `@agent-premortem-auditor`'s dispatch prompts; both agents
  read `command`, `predicate.result`, and `capturedAt` directly off records in this
  shape when citing an entry. A future `handback-skill` story reads this file before
  reading the log itself, same as this one did.
