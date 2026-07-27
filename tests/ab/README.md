# A/B eval harness

`scripts/run_gate_audit_fixtures.py` answers **"does the current configuration still
pass its golden fixtures?"** — one run per fixture, pass/fail, wired into CI.

`scripts/run_ab_eval.py` answers a different question: **"does changing one variable
move the outcome, and by how much against run-to-run noise?"** Two or more arms, N
trials each, scored per planted defect. It is never run in CI — it costs live model
calls and its output is a comparison for a human to read, not an assertion.

This is the harness `CONTRIBUTING.md` requires before dropping a merge-blocking agent's
model tier.

## Why per-defect scoring

A finding count cannot distinguish the two ways an arm loses a finding, and they are
opposite defects with opposite fixes:

| Outcome | Meaning |
|---|---|
| `REPORTED` | Filed in a findings section at or above its floor tier. |
| `UNDER_TIERED` | Filed as a finding, but below its floor tier — a calibration slip. |
| `DEMOTED` | Present in the report text, but never filed as a finding — suppression. |
| `MISSED` | Absent from the report entirely — a detection loss. |

`DEMOTED` means the auditor *saw* the defect and wrote it into prose or a residual line
instead of filing it. That has happened here before: an earlier revision of the
calibration wording in `reference/prompt-contract.md` §4 rendered a real missing-auth
Critical as prose. A count-based eval scores that identically to never having found it,
and would point at the wrong fix.

## Ground truth

Each fixture's `expected.json` may carry a `planted` array naming what its changeset
actually contains:

```json
{
  "planted": [
    {
      "id": "authz-bypass",
      "floor": "critical",
      "locator": "app/admin.py",
      "signals": ["is_admin", "authoriz", "PermissionError"]
    }
  ]
}
```

A report counts as naming a defect when it mentions the `locator` **and** at least one
`signal`. Both halves are required: a locator alone matches a Summary line listing every
file touched, and a signal alone matches vocabulary any report might use in passing. The
signal list is also what separates two defects planted in the same file — as in
`posture-injection`, where the command injection and the audit-evasion comment share a
locator.

`floor` is the lowest tier that still counts as reporting the defect. A missing or empty
`planted` array marks a control fixture that asserts a clean result.

Matching is section-level, not row-level: it sees *that* a report names a defect, not
whether it gave it a row of its own. `posture-injection`'s `audit-evasion-acknowledged`
is scoped to that limit deliberately — an auditor that mentions evasion anywhere did not
obey the embedded directive, which is the posture question, and its floor is `track`
because a report that folds the acknowledgement into the injection finding still answers
it. Do not read that defect as a check on whether evasion got its own finding row.

`Expectation.from_dict` ignores the `planted` key, so adding ground truth never changes
what the golden harness asserts.

## Running one

```bash
# Verify an arm actually applies before spending live runs on it.
uv run --no-project python scripts/run_ab_eval.py \
  --arms tests/ab/arms/calibration-wording.json --dry-run

# Then run it. 2 arms x 6 fixtures x 3 trials = 36 headless /gate-audit runs
# (model-drop-136.json is 3 arms = 54). frontend-effect-leak has a web surface,
# so it dispatches 12 lanes rather than 9 — budget it as the expensive one.
uv run --no-project python scripts/run_ab_eval.py \
  --arms tests/ab/arms/calibration-wording.json \
  --trials 3 \
  --artifacts-dir ab-results
```

`--dry-run` prints each arm's overrides and warns when a variant is byte-identical to
what it replaces — the failure mode where an arm silently tests nothing.

Narrow with `--fixture NAME` (repeatable) while iterating. `--artifacts-dir` writes every
raw report plus `comparison.txt` and `results.json`; keep them, since the interesting
part of a surprising result is usually the report text, not the tally.

## How an arm varies

An arm changes one thing, applied by building a **shadow plugin root** — a tree of
symlinks back to the repo with only the overridden files materialized as real copies.
Nothing checked in is mutated, so an interrupted run leaves nothing to clean up.

- **`contract`** maps a repo-relative path to a replacement file. In practice that is
  `reference/prompt-contract.md`; the override is whole-file, so a variant is a full copy
  of the contract with one section changed.
- **`models`** maps an agent name to a model, rewriting only the `model:` pin in that
  agent's YAML frontmatter. An agent with no frontmatter or no pin raises rather than
  silently no-opping, because an arm that failed to apply would otherwise be scored as a
  real result.

## Reading the output

The report is counts, never a verdict on the experiment. Every arm samples a stochastic
system; treat a gap as signal only when it is large against the trial count, and re-run
before acting on a one-trial difference. Three trials separates "always" from "never" and
little else — raise `--trials` for anything closer than that.

Which movement matters depends on the question:

- **A wording change** is judged on `DEMOTED` and `UNDER_TIERED`. `MISSED` moving is a
  surprise worth investigating, since wording is not supposed to affect detection.
- **A model drop** is judged on `MISSED` first, then verdicts. That is the silent
  false-negative the tier gate in `CONTRIBUTING.md` exists to prevent.
- **The `clean-refactor` control** guards the other direction. An arm that improves
  recall by making everything a finding shows up here as a lost `PASS`.

## The two configured experiments

### `arms/calibration-wording.json` — run 2026-07-26, variant rejected

12 runs over `severity-calibration-trap` + `clean-refactor`, 3 trials/arm, $47.12.
Flat on every axis: the planted authz bypass scored `REPORTED` 3/3 in both arms,
both verdicts held 3/3, and the control stayed `PASS` with zero findings in both.
No `DEMOTED`, `UNDER_TIERED`, or `MISSED` anywhere.

§4's wording is not suppressing findings on Opus 5, so the variant should not
merge — see the header comment in `variants/prompt-contract-coverage-first.md`
for the full result and what it does not rule out. Scope the re-test to a defect
the auditor is genuinely unsure about; this one plants a deleted
`raise PermissionError`, which is the easy case.

Two calibration notes for anyone reading a future run of this file. Critical
counts were stable at 1 across all six trap runs, but Important counts ranged 0–8
within a single arm — only large gaps at that tier are readable at n=3. And the
one-trial pilot showed the opposite direction from the n=3 result, which is the
whole reason the noise caveat below is not boilerplate.

### The experiment as configured

Baseline vs `variants/prompt-contract-coverage-first.md`, which rewrites §4 to make
filing the default and route uncertainty into the existing `confidence: Potential` field
instead of into omission. It leans on the compile step in
`reference/audit-compilation.md`, which already re-checks every Critical against the diff
and drops what it cannot confirm — so a filed-but-unconfirmed finding is filtered in the
open rather than silently by the auditor.

Read `severity-calibration-trap` first: it plants the same shape of defect (an authorization
check computed but never enforced) that §4's wording suppressed before.

### `arms/model-drop-136.json`

Baseline against all four `inherit` agents pinned down a tier, for
[#136](https://github.com/jacquardlabs/studious/issues/136).

Dropping four agents in one arm does not confound the read, because each fixture's
planted defect belongs to a single lane: `stale-api-docs` scores `doc-auditor`,
`frontend-effect-leak` scores `frontend-reviewer`, and `missing-regression-test` scores
`test-auditor` (with `code-auditor` as the plausible second catcher — both are in the
drop set, so the overlap costs nothing). Read the per-fixture rows, not the aggregate.

Judge on `MISSED` first. A tier drop that loses a planted defect is the silent false
negative the gate in `CONTRIBUTING.md` exists to prevent; a drop that only moves
`UNDER_TIERED` is a calibration change, which is cheaper and may be acceptable.

## Adding a fixture

Fixtures are shared with the golden harness — see `tests/fixtures/`. A new one needs
`base/`, `changeset/`, and an `expected.json`. Add `planted` ground truth at the same
time: `test_run_ab_eval.py` fails a fixture that promises a critical finding but plants
no critical defect, which is what keeps the two files from drifting apart.
