# Build report — coach-skill (M6 — Coach)

- Story: coach-skill (issue #21), epic `m6-coach`
- Branch: `epic/m6-coach` at `3a620d2` (merge of `epic/m6-coach--coach-skill`)
- Date: 2026-07-17 (UTC)
- Pipeline: studious `/work-through` drove the story end to end (design →
  design-review → build → audit → acceptance). jig's `/build` loop was not
  used: no `PLAN.md`, no `docs/jig/evidence/` capture, and no
  `verify:results` exist for this story. Everything below is gate-verdict
  evidence, named as such — never substituted for `/build` evidence that
  doesn't exist.

## Verdict trail

design: done → design-review: PROCEED TO PLAN → build: done → audit: PASS
→ acceptance: SHIP

Finale, recorded at `3a620d2`: `/gate-audit` PASS (0 Critical, 2 Important,
remainder Track) · `/gate-acceptance` SHIP (one non-blocking OBSERVATION) ·
pre-mortem registers (story + epic): every item NOT REALIZED. Test suite at
acceptance: 390 passed, 1 skipped (PyYAML absent).

## Evidence table

Links anchor to commit `3a620d2` — the design doc and demos are removed by
`/finish` cleanup after this report and stay readable at that SHA.

| # | Acceptance criterion | Verification | Evidence | Pass |
|---|---|---|---|---|
| 1 | Invocation convention decided and shipped; STUB frontmatter and "do not invoke" gone (DESIGN.md risk #4 closed) | design fork ruling + gates | `docs/design/coach-skill.md` §Invocation convention (option A ruled); DESIGN.md updated on this branch; `skills/coach/SKILL.md` frontmatter | SHIP |
| 2 | Evidence-based state assessment demonstrated against ≥3 pipeline states | committed demos, reproduced by the acceptance gate | 5 states under `docs/jig/demonstrations/2026-07-17-coach-skill/` (no-artifacts, post-plan, mid-build-paused, escalate, repo-contradicts-conversation) + `setup.sh`; acceptance reproduced all five with real status-flip suffixes | SHIP |
| 3 | Exactly ONE next action with why, rough cost, path ahead — coach, not menu | SKILL.md Step 2 + demo transcripts | routing table (observed state → one action); fixed cost vocabulary | SHIP |
| 4 | Pocock rule: dispatch only on explicit same-turn confirmation, one at a time, never chained | SKILL.md Step 3 + acceptance walkthrough | demos stop at the confirmation question — an unattended session cannot fabricate the human "yes" the skill enforces (documented limitation, not a defect) | SHIP |
| 5 | Context passed explicitly: `/plan` gets the design doc, `/build` the plan path, `/design` revision mode the ESCALATE finding | pre-mortem verification | epic register item 1 NOT REALIZED — dispatch context checked against the landed SKILL.md contracts, not the handoff | SHIP |
| 6 | Shortcuts honored with skipped steps named | SKILL.md §Shortcuts are first-class | quick-path wording names every skipped step | SHIP |
| 7 | Does no work itself: no writes, no status flips, no verdicts | SKILL.md §Does no work itself + pre-mortem | read-only tool enumeration; epic register item 2 NOT REALIZED | SHIP |
| 8 | Degrades gracefully without studious, degradation named | routing table + pre-mortem | per-row studious-absent lines; epic register item 6 NOT REALIZED | SHIP |

## Freshness hold

`scripts/evidence-freshness` had zero evidence folders to validate for this
story (no `evidence-capture` ever ran on it) — vacuously clean, reported
rather than assumed. The `docs/jig/evidence/2026-07-17-*` folders on the
branch belong to main's replay-bundle feature (#78), not this story.

## cctx footer

cctx not installed; session-cost footer and harvest offer skipped
(`pipx install cctx-cli` to enable).

## Follow-ups filed

`PLAN.md` Not-here follow-ups and NOTES stubs were both absent (no
`PLAN.md`; 0 stubs found) — zero survivors from `/finish`'s two standard
sources, an honest result. Three issues were filed from the M6 finale
audit instead, each confirmed per-item:

- [#79](https://github.com/jacquardlabs/jig/issues/79) — Collapse the six `derive_*_vocabulary` clones into one `_derive_vocabulary` helper (Important, code-auditor)
- [#80](https://github.com/jacquardlabs/jig/issues/80) — Coach reads `## Revision History` presence as signed-off — REVISED docs false-positive (Important, architecture-auditor)
- [#81](https://github.com/jacquardlabs/jig/issues/81) — README still lists the coach invocation convention as undecided (Track, doc-auditor)

None skipped; no filing failures.

## Decision patches

None proposed. The one ruled fork with lasting consequences — invocation
convention → `/coach`, user-invoked on an explicit ask only — was written
into DESIGN.md on this branch by the story itself (Command-naming bullet
updated; risk #4 marked closed). PRODUCT.md's broader staleness ("no skill
has real behavior yet") predates this branch and belongs to
`/deep-review product`.

## Cleanup and verdict

Removed at `/finish` cleanup, after this report: `docs/design/coach-skill.md`
and `docs/jig/demonstrations/2026-07-17-coach-skill/` (both readable at
`3a620d2`). Verdict: **PR** → `main`, opened from `epic/m6-coach`; worktree
kept at `.studious/worktrees/m6-coach/__epic`, branch kept and tracked by
the PR.
