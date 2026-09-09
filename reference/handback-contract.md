<!-- Contract, not a door. Moved out of the command surface by the persona
     restructure; the door that reads it is named in the first paragraph. -->

# Hand back this branch's evidence

Turns the harness-captured evidence log (`.studious/evidence/<branch-slug>.jsonl`, written
by `hooks/evidence-capture.sh` while a story is armed) plus a written narrative into one
committed file on the branch, per `reference/worker-contract.md`'s requirement to return
"a summary" and "evidence — commands actually run with their captured output."

Not a gate: emits no verdict, records nothing to `.studious/`, isn't in
`reference/gate-vocabulary.md`. It's a worker action, using the same commit authority a
worker already exercises for its own code (`reference/worker-contract.md`: "the work,
committed... uncommitted work does not exist").

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

Must match `bin/gate-ledger`'s `branch_slug()` byte for byte — it's the key both the
evidence log and manifest file are filed under. Don't re-derive with different logic (e.g.
`sed`/regex) that could diverge on an edge case; the `tr` form above is the whole rule.

## 2. Read the evidence log

```bash
gate-ledger evidence-list --branch "$branch"
```

Always pass `--branch` explicitly (never rely on the tool's current-branch default) — this
may run from a worktree checked out to a different branch. This is the *only* way to read
the log: it resolves the same `evidence_dir()` that `evidence-append` writes through, so a
linked story worktree still finds records in the shared main-tree store. Never read
`.studious/evidence/*.jsonl` directly or re-derive the branch-slug/repo-root logic —
one place that store's location lives.

Deliberately **do not** pass `--dedupe` (unlike `/review`'s and `/review --delivery`'s
evidence dispatches) — a handback manifest is a complete historical record across every
fix cycle, not current-state-only.

## 3. No log, or an empty one — report and stop

If step 2 printed nothing, distinguish two states before reporting — do not collapse them
into one message:

- **Not armed** — no work file known to `gate-ledger` has `.branch` equal to the target
  branch (`gate-ledger work-list`'s third column, exact match): evidence capture never had
  a story to attach records to, so nothing was captured regardless of what ran. Report:

  > No work file is armed for `<branch>` — evidence capture was never on for this branch,
  > so nothing was captured regardless of what ran. Register the branch first (`/next`
  > or `gate-ledger work-set --slug <slug> --branch <branch>`) if you expected a log
  > here.

- **Armed, but the log is missing or empty** — a work file does claim this branch, but no
  verification commands were captured. Report exactly:

  > No evidence log found for `<branch>` — no verification commands were captured on this
  > branch.

Either way: write nothing, commit nothing, stop here. Do not create a stub or placeholder
file "for completeness" — an absent log is a fact to report, not a gap to paper over.

## 4. A non-empty log — assemble the manifest

Write (or overwrite) `docs/studious/handback/<slug>.md`. Check first (`Read`/`Glob`)
whether it exists — if so, this is a regeneration; note that in the file and the step 7
report. Re-running `/ship --handback` on the same branch always overwrites and recommits
this one file rather than accumulating dated copies: the evidence log is append-only, so a
later manifest is always a superset of an earlier one, and git history preserves every
prior snapshot.

Structure, top to bottom:

```markdown
# Handback — <branch>

> Worker-authored evidence record, assembled by `/ship --handback` — not a Studious gate verdict
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

Capture the evidence log once; derive the manifest rows and all three header counts from
that single value rather than re-invoking `gate-ledger evidence-list` per derivation:

```bash
evidence_log=$(gate-ledger evidence-list --branch "$branch")
```

**Manifest rows.** One row per JSONL record from step 2, in printed order (already
chronological — the log is append-only). Populate columns from these fields only —
`capturedAt`, `command`, `predicate.result`, `origin`, `outputDigest` — per
`reference/evidence-format.md`'s pinned shape. Never read or print any other field, and
never fall back to raw stdout/stderr if a digest is missing — the schema stores no raw
output, only a digest, to avoid re-exposing what a failed command's output might have
echoed (a token, a stack trace). An absent or empty `outputDigest` renders as the literal
placeholder `_(no digest captured)_`, never blank or another field's value. Wrap the
command in backticks and escape any literal `|` as `\|` so a piped command doesn't break
the table row:

```bash
printf '%s\n' "$evidence_log" | jq -r '
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

Record/pass/fail counts for the header line, derived from the same `$evidence_log`:

```bash
total=$(printf '%s\n' "$evidence_log" | wc -l | tr -d ' ')
passed=$(printf '%s\n' "$evidence_log" | jq -r '.predicate.result' | grep -c '^PASSED$' || true)
failed=$(printf '%s\n' "$evidence_log" | jq -r '.predicate.result' | grep -c '^FAILED$' || true)
```

**Summary prose.** Grounded in real artifacts on the branch, never invented (PRODUCT.md's
"Evidence over invention"):

- `git log <merge-base>..<branch> --oneline` (merge-base against the default branch, e.g.
  `git merge-base <branch> origin/main`, falling back to `origin/master` or the repo's
  actual default branch) — what actually changed.
- The design doc, if recorded (`gate-ledger work-list` for a matching `.branch`, then
  `gate-ledger work-get --slug <slug>` for `.designDoc`) — what the branch is supposed to
  do. If none exists, say so rather than guessing; ground the summary in the diff and
  evidence alone.
- The evidence entries themselves — what was actually verified, and whether it passed.

Say what changed and why, and call out anything the pass/fail split alone doesn't show (a
targeted regression test for a specific fix, a lint pass covering only part of the diff).
The record counts are a floor, not a replacement — "N commands ran, M passed" alone adds
nothing the manifest table doesn't already show.

## 5. Write and commit

Write the file, then:

```bash
git add docs/studious/handback/<slug>.md
git commit -m "docs: handback evidence manifest for <branch>"
```

This is the worker's own commit authority (`reference/worker-contract.md`) — the same
authority already used for the worker's own code and, at the design-review gate, for the
pre-mortem register.

## 6. If `gate-ledger` is missing

If `gate-ledger` is not on `PATH` (the plugin's `bin/` isn't resolvable), say so and stop —
do not fall back to reading `.studious/evidence/*.jsonl` directly. That file's location is
`evidence_dir()`'s to own (see step 2).

## 7. Report back

State plainly:

- The no-log message from step 3, or
- The file path, record count, and pass/fail split, plus — if this run overwrote an
  existing file — a one-line note that it was regenerated and the prior version is in git
  history.

Nothing else advances — this command doesn't touch `.studious/` state, doesn't set a
work-file phase, and doesn't imply any gate ran.
