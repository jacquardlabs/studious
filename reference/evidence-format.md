# Evidence record format — the harness-captured verification log

`hooks/evidence-capture.sh` and `bin/gate-ledger`'s `evidence-append` verb write one
JSON object per line to `.studious/evidence/<branch-slug>.jsonl` for every verification
command run while a story is armed. This file pins the exact shape, and how far this
story goes into winnow's evidence format, so a later story extending it has one place
to check against instead of re-deriving scope from the amendment itself.

## Scope: winnow Amendment 006's early footprint only

Source: `docs/amendments/006-evidence-bundles.md` in the sibling `winnow` repo (itself
"Proposed — pending owner adoption" there, not a frozen spec), "Early footprint (cheap
now, structural later)" section. This story implements exactly its two rules and
nothing past them:

1. **Capturer provenance**, recorded on every record — `capturer: "hook"` in v0, a
   constant, because Studious has no persistent daemon process the way winnow's design
   assumes.
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
| `capturedAt` | `now_iso()` inside `bin/gate-ledger`, not a caller-supplied flag | UTC, `%Y-%m-%dT%H:%M:%SZ` |
| `capturer` | Hardcoded `"hook"` inside `cmd_evidence_append` | Not a flag — no caller can write a different capturer value. The field that makes capturer ≠ claimant checkable, per the amendment. |
| `origin` | `"subagent"` if the hook input's `agent_id` is present, else `"interactive"` | See "Open item: origin and /next's actual dispatch mechanism" below — a real, currently-unverified gap. |
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

The design doc's open question — "the exact `tool_response` field for Bash exit
status" — had no answer: the premise was wrong. Verified against
`code.claude.com/docs/en/hooks` (the raw page content, not a summary): a Bash tool call
does **not** always fire `PostToolUse`. It fires exactly one of two distinct events, with
non-overlapping input schemas:

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

## Open item: `origin` and `/next`'s actual dispatch mechanism

`agent_id`/`agent_type` are documented as present "only when the hook fires inside a
subagent call" — a Claude Code Task-tool-dispatched subagent within one session.
Confirmed from the docs.

This is dogfood item zero's real remaining surface — the mechanism-level question
(whether `PostToolUse`/`PostToolUseFailure` fire for Bash calls inside a subagent) is
already resolved above. `tests/test_evidence_capture.sh` verifies everything
mechanically checkable without a live dispatch: the hook resolves the armed check and
writes to the **shared main-tree** evidence store from a **linked worktree** cwd
(mirroring a worker's actual cwd), and `origin` resolves to `"subagent"` given an
`agent_id`-bearing payload. Unverified: whether a real `/next` dispatch populates
`agent_id` — issue #97's dogfood plan (studyengine #210, then #209) is the intended
validation loop; update this section once that run produces an answer.

## The producer-side store: `scripts/evidence-capture` artifact labels

Separate from the log above. `/build` captures per-task artifacts through
`scripts/evidence-capture --task <id> --artifact PRODUCER:LABEL=PATH` into the main
checkout's gitignored build-evidence store; `/ship` Step 1 quotes captured text artifacts
into the PR body, which is how they reach a judge. Labels in use, each pinned where its
producer is described in `skills/build/SKILL.md`: `verify:results`, `inspector:report`,
`build:replay-bundle` (Step 2), and `exorcist:report` (Step 3) — the report
`/exorcist:exorcise` prints, captured under `--task exorcise` only after the post-exorcise
`verify` re-run passed and the `exorcise:` commit landed — or, when the pass left the tree
clean, with neither, since there is nothing to re-verify or commit. Its `## Held` section
is the one route a `hold` finding takes to `/review`; no separate findings format exists
for it.

## Reading the log: `evidence-list`

`studious evidence-list [--branch B] [--dedupe]` is the one read verb for this
store, added by `handback-skill` (`reference/handback-contract.md`). It resolves the branch's
`.jsonl` path through the same `evidence_dir()`/`branch_slug()` functions
`evidence-append` already writes through and prints the file verbatim — nothing if
it's absent — so no caller re-derives repo-root/slug anchoring on the read side
either. `gates-cite-evidence`, when it lands, reuses this verb rather than adding a
second reader; see "Consumers that must stay in sync" below.

**`--dedupe`** (added by story `evidence-list-dedupe`, issue #162) collapses output to
one record per distinct `command` value — the *last*-appended one — in the survivors'
original relative order; it only changes which records are selected, never a record's
shape. Long-running branches accumulate one line per verification command per fix
cycle, most superseded by a later re-run of the same command; `--dedupe` avoids a
test-auditor/premortem-auditor dispatch citing a stale record, without changing what a
gate is allowed to conclude. **Requires `jq`** (unlike the plain, dependency-free read)
and **fails closed**: no `jq`, or a malformed line, means no stdout and a non-zero
exit — never a plausible-looking partial result. Every `evidence-list` caller already
treats an error identically to empty output, so a `--dedupe` failure needs no new
caller-side handling. `commands/review.md` reads the `--dedupe` form once before
dispatching any judge; `reference/handback-contract.md` keeps reading the raw
(non-deduped) form, since its manifest's job is a complete history, not
current-state-only.

## Consumers that must stay in sync

- `tests/test_gate_ledger.sh`'s `evidence-append` tests assert the exact key set and
  ordering above — update both together.
- `tests/test_evidence_capture.sh` asserts the hook produces this shape end to end,
  including the `PostToolUse`/`PostToolUseFailure` split.
- `tests/test_gate_ledger.sh`'s `evidence-list` tests assert it reads through the
  same anchoring `evidence-append` writes through, including from a linked
  worktree — update both together.
- `tests/test_gate_ledger.sh`'s `evidence-list --dedupe` fixture asserts the
  collapsed record count is smaller than the raw count, that it equals the number of
  distinct commands, and that each distinct command's surviving record is its
  **last**-appended one — update both together.
- `reference/handback-contract.md` reads this file's pinned shape before assembling its
  manifest table (timestamp, command, `predicate.result`, origin, `outputDigest`
  only — never any other field).
- `studious evidence-list` is a plain passthrough of this shape, one line per
  record (or, with `--dedupe`, one line per distinct `command`) — neither mode
  reshapes a record, only which ones are selected. `commands/review.md` passes its
  `--dedupe` output to every judge invocation as `receipts_path`; a judge such as
  `gauntlet:test-auditor` or `gauntlet:premortem-auditor` reads `command`,
  `predicate.result`, `capturedAt`, and `outputDigest` directly off records in this
  shape when citing an entry.
