---
description: Assemble a branch's evidence manifest and a written summary, then commit them — closes out a worker's return per reference/worker-contract.md
argument-hint: "[branch] (omit to use the current branch)"
allowed-tools: Read, Glob, Grep, Bash, Write
---

# Hand back this branch's evidence

`reference/worker-contract.md` requires a worker to return "a summary" and "evidence —
commands actually run with their captured output." Today that return is prose in a chat
transcript: read once, then gone. This command turns the harness-captured evidence log
(`.studious/evidence/<branch-slug>.jsonl`, written by `hooks/evidence-capture.sh` while a
story is armed) plus a written narrative into one committed file on the branch, so a later
reader — a human, a gate, a future session picking the branch back up — has one place to
read "what happened here" instead of reconstructing it from git log and a vanished
transcript.

This is not a gate. It emits no verdict, records nothing to `.studious/`, and isn't in
`reference/gate-vocabulary.md`. It's a worker action — the same commit authority a worker
already exercises for its own code (`reference/worker-contract.md`: "the work, committed...
uncommitted work does not exist").

## 1. Resolve the target branch

`$ARGUMENTS`, if given, names the branch. Otherwise use the current branch
(`git rev-parse --abbrev-ref HEAD`). Do not check out a different branch to run this
command — `gate-ledger evidence-list --branch` and `git log <branch>` both read a named
branch's data without switching.

Derive its slug exactly the way `gate-ledger` does — every `/` replaced with `-`, nothing
else:

```bash
slug=$(printf '%s' "$branch" | tr '/' '-')
```

This must match `bin/gate-ledger`'s own `branch_slug()` byte for byte, since it's also the
key the evidence log and the manifest file are both filed under. Don't re-derive this with
different logic (e.g. `sed`/regex substitution) that could diverge on an edge case
`branch_slug()` handles differently — the `tr` form above is the whole rule.

## 2. Read the evidence log

```bash
gate-ledger evidence-list --branch "$branch"
```

Always pass `--branch` explicitly (never rely on the tool's own current-branch default) —
this command may run from a worktree checked out to a different branch than the one being
handed back. This is the *only* way to read the log: it resolves the same `evidence_dir()`
anchoring `evidence-append` already writes through, so a linked story worktree still finds
records filed against the shared main-tree store. Never read
`.studious/evidence/*.jsonl` directly or re-derive the branch-slug/repo-root logic here —
one place that store's location lives.

## 3. No log, or an empty one — report and stop

If step 2 printed nothing, this branch has no evidence to hand back. **Before reporting,
distinguish two states a user must be able to tell apart** — do not collapse them into one
message:

- **Not armed** — no work file known to `gate-ledger` has `.branch` equal to the target
  branch (`gate-ledger work-list`'s third column, exact match). Evidence capture never had
  a story to attach records to here; a worker could have run any number of commands and
  none would have been captured. Report:

  > No work file is armed for `<branch>` — evidence capture was never on for this branch,
  > so nothing was captured regardless of what ran. Register the branch first (`/work-on`,
  > `/work-through`'s driver, or `gate-ledger work-set --slug <slug> --branch <branch>`) if
  > you expected a log here.

- **Armed, but the log is missing or empty** — a work file does claim this branch, but no
  verification commands were captured. Report exactly:

  > No evidence log found for `<branch>` — no verification commands were captured on this
  > branch.

Either way: write nothing, commit nothing, stop here. Do not create a stub or placeholder
file "for completeness" — an absent log is a fact to report, not a gap to paper over.

## 4. A non-empty log — assemble the manifest

Write (or overwrite) `docs/studious/handback/<slug>.md`. Before writing, check whether the
file already exists (`Read`/`Glob`) — if it does, this is a regeneration; note that in both
the file and your final report (see step 7). Re-running `/handback` on the same branch
always overwrites and recommits this one file rather than accumulating dated copies: the
evidence log only grows (append-only), so a later manifest is always a superset of an
earlier one, and git history already preserves every prior snapshot.

Structure, top to bottom:

```markdown
# Handback — <branch>

> Worker-authored evidence record, assembled by `/handback` — not a Studious gate verdict
> and not reviewed by one. See `docs/studious/premortems/` for review-agent output.

- Branch: `<branch>`
- Generated: <ISO-8601 timestamp, `date -u +%Y-%m-%dT%H:%M:%SZ`>
- Records: <N> (<P> passed, <F> failed)
<- If regenerating: "- Regenerated — earlier versions of this file remain in `git log -- docs/studious/handback/<slug>.md`.">

## Evidence manifest

| Timestamp | Command | Result | Origin | Output digest |
|---|---|---|---|---|
<one row per record, oldest first, in the order evidence-list printed them>

## Summary

<written prose — see below>
```

**Manifest rows.** One row per JSONL record from step 2, in the order printed (the log is
append-only, so that's already chronological). Populate columns from these fields only —
`capturedAt`, `command`, `predicate.result`, `origin`, `outputDigest` — per
`reference/evidence-format.md`'s pinned shape. Never read or print any other field, and
never fall back to raw stdout/stderr if a digest looks missing — the schema doesn't store
raw output at all, only a digest exists to inspect a run without re-exposing whatever a
failed command's output might have echoed (a token, a stack trace). An absent or empty
`outputDigest` renders as the literal placeholder `_(no digest captured)_`, never blank and
never another field's value. Wrap the command in backticks and escape any literal `|` in it
as `\|` so a piped command doesn't break the table row. This jq pipeline does exactly that
(verified against a live evidence log while building this command):

```bash
gate-ledger evidence-list --branch "$branch" | jq -r '
  ((.outputDigest // "") as $d |
   [
     .capturedAt,
     ("`" + (.command | gsub("\\|"; "\\|")) + "`"),
     .predicate.result,
     .origin,
     (if $d == "" then "_(no digest captured)_" else $d end)
   ] | "| " + join(" | ") + " |")
'
```

Record/pass/fail counts for the header line:

```bash
total=$(gate-ledger evidence-list --branch "$branch" | wc -l | tr -d ' ')
passed=$(gate-ledger evidence-list --branch "$branch" | jq -r '.predicate.result' | grep -c '^PASSED$' || true)
failed=$(gate-ledger evidence-list --branch "$branch" | jq -r '.predicate.result' | grep -c '^FAILED$' || true)
```

**Summary prose.** Written by you, grounded in real artifacts already on the branch — not
invented (PRODUCT.md's "Evidence over invention" governs this the same way it governs
context-doc extraction):

- `git log <merge-base>..<branch> --oneline` (merge-base against the default branch, e.g.
  `git merge-base <branch> origin/main`, falling back to `origin/master` or the repo's
  actual default branch) — what actually changed.
- The design doc, if one is recorded (`gate-ledger work-list` for a work file whose
  `.branch` matches, then `gate-ledger work-get --slug <slug>` for its `.designDoc`) — what
  the branch is supposed to do. If no work file or no recorded design doc exists, say so in
  the summary rather than guessing at one; ground the summary in the diff and evidence
  alone.
- The evidence entries themselves — what was actually verified, and whether it passed.

Say what changed and why, and call out anything the record/pass-fail split alone doesn't
show (a targeted regression test added for a specific fix, a lint pass that only covers
part of the diff). The record counts are a floor this section can lean on, not a
replacement for it — "N commands ran, M passed" with nothing else is exactly what the
manifest table already shows without a summary at all.

## 5. Write and commit

Write the file, then:

```bash
git add docs/studious/handback/<slug>.md
git commit -m "docs: handback evidence manifest for <branch>"
```

This is the worker's own commit authority (`reference/worker-contract.md`), not a new one
Studious is granting itself here — the same authority already used for the worker's own
code and, at the design-review gate, for the pre-mortem register.

## 6. If `gate-ledger` is missing

If `gate-ledger` is not on `PATH` (the plugin's `bin/` isn't resolvable in this
environment), say so plainly and stop — do not fall back to reading
`.studious/evidence/*.jsonl` directly. That file's location and anchoring are
`evidence_dir()`'s to own; reading around it here would silently duplicate logic this
command specifically exists to avoid duplicating (see step 2).

## 7. Report back

State plainly:

- The no-log message from step 3, or
- The file path, record count, and pass/fail split, plus — if this run overwrote an
  existing file — a one-line note that it was regenerated and the prior version is in git
  history.

Nothing else advances. This command doesn't touch `.studious/` state, doesn't set a
work-file phase, and doesn't imply any gate ran.
