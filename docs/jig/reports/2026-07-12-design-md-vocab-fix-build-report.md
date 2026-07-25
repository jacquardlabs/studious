# /finish — build/design-md-vocab-fix-202607122225

Verdict: **PR** against `main`. This branch fixes issue
[#47](https://github.com/jacquardlabs/jig/issues/47) (DESIGN.md's
`/build` task-status vocabulary miscategorized `FIX` as a fourth terminal
status and omitted `RESAMPLE` entirely) and is the M5 (`/finish`) epic's
**second** required-demonstration build: it exercises `/finish`'s `PR`
verdict for real (worktree kept, branch kept un-merged, a real GitHub PR
opened), distinct git/GitHub mechanics from the first demonstration's
`MERGE` verdict.

## Step 1 — PR evidence table

Evidence folder: `docs/jig/evidence/2026-07-12-design-md-vocab-fix/` (commit
`3f72252a5602cec029e329d5df93822ce374d028`). Freshness hold
(`scripts/evidence-freshness`): **PASS** — floored on the folder's own
manifest commit, not the branch's current `HEAD` (which has since
advanced through the evidence-capture and status-flip commits).

| # | Done means item | Method | Evidence | Pass |
|---|---|---|---|---|
| 1 | DESIGN.md's `/build task status` row lists PASS/REPLAN/ESCALATE (no FIX) and sources to `skills/build/SKILL.md` | script | see below | PASS |
| 2 | DESIGN.md documents FIX and RESAMPLE as the failure routine's two transient actions | script | see below | PASS |
| 3 | full test suite (`tests/`) still passes | test-backed | see below | PASS |

<details>
<summary>Item 1 — task-status row corrected (script)</summary>

```
command: grep -qF '| `/build` task status | `todo` → `in-progress` → `PASS`/`REPLAN`/`ESCALATE` | `skills/build/SKILL.md` |' DESIGN.md
exit code: 0
```
</details>

<details>
<summary>Item 2 — FIX/RESAMPLE row added (script)</summary>

```
command: grep -qF '| `/build` failure-routine action | `FIX` \| `RESAMPLE` | `skills/build/SKILL.md` |' DESIGN.md
exit code: 0
```

(First verify attempt against this item FAILed on a Foreman transcription
bug — the command checked for an un-escaped `|` between `FIX` and
`RESAMPLE`, but DESIGN.md's own table-cell convention escapes an interior
pipe as `\|`, matching the file's existing rows. Corrected the item's own
command and re-ran `verify`; no new executor dispatched, since the
underlying work was already correct — the same "Foreman's own bug, fix
the transcription, retry" path `skills/build/SKILL.md` names for a
`verify` usage error, applied here to a mis-transcribed expected-value
rather than a malformed items file.)
</details>

<details>
<summary>Item 3 — full test suite (test-backed)</summary>

```
command: uv run --no-project python3 -m unittest discover -s tests -v
exit code: 0
Ran 97 tests in 5.293s
OK (skipped=1)
```

(97, not 145 — this branch bases on `main`, which predates the M5 epic's
own test files (test_finish_skill.py, test_evidence_freshness.py, etc.);
expected and correct for a branch built off `main`.)
</details>

No `Done means` item lacked an evidence folder.

## Step 2 — cctx footer

cctx not installed; skipping the session-cost footer and harvest offer.
Install with `pipx install cctx-cli`.

## Step 3 — File survivors

`PLAN.md`'s `## Not-here follow-ups` section named 1 item, drafted and
presented for confirmation:

| Draft | Decision | Result |
|---|---|---|
| Re-point DESIGN.md's other Vocabulary rows to their shipped SKILL.md, not the handoff | Accepted | Filed as jacquardlabs/jig#56 |

NOTES stubs: 0 found.

## Step 4 — Proposed decision patches (never applied)

None proposed. This task's own deliverable was a direct DESIGN.md
correction (the shipped fix itself), not a build-time judgment call that
outlives the branch and needs a separate context-doc patch.

## Step 5 — This report

Written by `scripts/build-report --repo <worktree> --slug
design-md-vocab-fix --content <this file>` to
`docs/jig/reports/2026-07-12-design-md-vocab-fix-build-report.md`,
committed as its own commit, distinct from Step 6's cleanup commit.

## Step 6 — Verdict + cleanup

**PR** against `main` — this branch was created with `--base main`
(`build/design-md-vocab-fix-202607122225` diverges directly from `main`,
which is the repo's one well-known default branch: base-branch resolution
rule 3).

- Worktree: kept (follow-up commits addressing review feedback still need
  it).
- Branch: kept, un-merged, tracked by the open PR.
- PR: opened via `gh pr create` against `main`, carrying this report's own
  Step 1–4 content as its description.
