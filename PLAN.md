# Plan: rescope the recommend-only invariant

Drafted by `/plan` against `docs/design/recommend-only-invariant-scope.md`
(issue #257). Extracted from the design doc: **problem** — "Problem &
persona" (CLAUDE.md:77 and CONTRIBUTING.md:46 both claim commands never
modify external state; false on three shipped surfaces); **approach** —
"Proposed design" (three files change, prose-only, no code: CLAUDE.md's
"Recommend-only" bullet becomes three labeled bullets, CONTRIBUTING.md:46-47
cites CLAUDE.md instead of restating, `reference/decision-journal-format.md:15-16`
is corrected); **load-bearing constraints** — "Alternatives considered"'s
Q1-Q8 decisions (two-tier split chosen, `docs/studious/` exemption stays
implicit, `/handback` dropped from the violator list, #247's carve-out
stated now, the decision-journal claim corrected not deleted, CONTRIBUTING.md
cites rather than restates, the ~9-file site sweep deferred to #255) are
treated as settled, not reopened here. "Out of scope" is exactly that:
the site sweep, un-parking #247, a CI mechanical check, and `/handback`.

Spine: Task 1, Task 2, and Task 3 are independent edits to three separate
files and may happen in any order; Task 4 rests on all three and verifies
the finished set together.

### Task 1 — Replace CLAUDE.md's "Recommend-only" bullet with the three-bullet rescope [PASS]
Why now:    CLAUDE.md:77 states the invariant this whole story exists to fix; it's the canonical text the other two files' edits point back to.
Read first: `CLAUDE.md`, `docs/design/recommend-only-invariant-scope.md`
Rests on:   n/a -- independent of Task 2 and Task 3.
Do:         replace CLAUDE.md:77's single "Recommend-only" bullet under "Key invariants when adding or changing prompts" with the three labeled bullets from the design doc's "Proposed design" section, verbatim (block-quoted there under the `> -` markers).
Not here:   no edits to CONTRIBUTING.md or `reference/decision-journal-format.md` -- separate tasks.

Done means:
1. [cap]  `CLAUDE.md` contains the bullet titled "Recommend-only means propose, never modify."   (tier: probe)
2. [cap]  `CLAUDE.md` contains the bullet titled "One bookkeeping boundary, not a name list."   (tier: probe)
3. [cap]  `CLAUDE.md` contains the bullet titled "Everything else is either an executor or a human-typed one-off."   (tier: probe)
4. [cap]  the first bullet names both `/backlog-hygiene` and `/backlog-priorities`   (tier: probe)
5. [hold] the adjacent "Stay in lane" bullet is untouched   (tier: probe)
Evidence: (recorded by `scripts/evidence-capture` once `/build` executes this task; none yet -- this plan has not been built)

### Task 2 — CONTRIBUTING.md: cite CLAUDE.md instead of restating; drop the now-redundant sentence
Why now:    CONTRIBUTING.md:46 currently restates the same false claim as CLAUDE.md:77; Q6 settled that this file should cite the canonical source instead, matching this repo's own established pattern.
Read first: `CONTRIBUTING.md`, `docs/design/recommend-only-invariant-scope.md`
Rests on:   n/a -- independent of Task 1 and Task 3.
Do:         replace CONTRIBUTING.md:46 with the citation-only bullet from the design doc; delete CONTRIBUTING.md:47's trailing sentence ("The `.studious/` exception above extends to `/work-through`...") while keeping that bullet's first three sentences ("Workers never gate; gates never build." through "...must never write code.") unchanged.
Not here:   no edits to the Naming conventions section (CONTRIBUTING.md:53) or anything else in the file.

Done means:
1. [cap]  `CONTRIBUTING.md:46`'s bullet cites CLAUDE.md's "Key invariants," recommend-only bullets instead of restating the invariant's own text   (tier: probe)
2. [cap]  `CONTRIBUTING.md:47`'s "Workers never gate; gates never build" bullet still opens with that exact sentence   (tier: probe)
3. [hold] `CONTRIBUTING.md`'s Naming conventions section (`CONTRIBUTING.md:53`) is untouched   (tier: probe)
Evidence: (recorded by `scripts/evidence-capture` once `/build` executes this task; none yet -- this plan has not been built)

### Task 3 — Correct reference/decision-journal-format.md's false commit-scope claim
Why now:    line 16's "Studious never runs `git commit` in a consuming project" is false -- `/gate-design-review` and `/gate-acceptance` both commit a file before recording, and `/build`/`/finish` commit as their normal operation; Q5 settled correcting rather than deleting it.
Read first: `reference/decision-journal-format.md`, `docs/design/recommend-only-invariant-scope.md`
Rests on:   n/a -- independent of Task 1 and Task 2.
Do:         replace `reference/decision-journal-format.md:15-16`'s false sentence with the corrected paragraph from the design doc, naming both the gate incidental-commit exception (citing CLAUDE.md's bookkeeping-boundary bullet) and the executor implementation-commit exception (citing `reference/worker-contract.md`); leave line 92-93's existing cross-reference to CLAUDE.md's recommend-only invariant unchanged -- it's already accurate against the new text.
Not here:   no edits to the Record shape section or the Consumers-that-must-stay-in-sync list beyond confirming line 92 needs no change.

Done means:
1. [cap]  `reference/decision-journal-format.md` states the journal "is never auto-committed by any Studious process"   (tier: probe)
2. [cap]  the corrected paragraph cites both CLAUDE.md's bookkeeping-boundary bullet and `reference/worker-contract.md`   (tier: probe)
3. [hold] line 92's "CLAUDE.md's recommend-only invariant names this journal as a sanctioned gate write" cross-reference is still present, unchanged   (tier: probe)
Evidence: (recorded by `scripts/evidence-capture` once `/build` executes this task; none yet -- this plan has not been built)

### Task 4 — Re-verify citations and run repo-wide doc checks against all three files
Why now:    the three edits are independently correct in isolation, but nothing else in this repo mechanically checks these citations, and CI's own reference/plugin checks run against whatever the three files say once this task lands.
Read first: `bin/gate-ledger`, `commands/work-through.md`, `commands/gate-should-we-build.md`, `commands/backlog-hygiene.md`, `commands/backlog-priorities.md`
Rests on:   Task 1, Task 2, Task 3 -- all three files must already carry their new text.
Do:         re-check every citation in CLAUDE.md's new second bullet (`bin/gate-ledger:220-231`'s `ensure_gitignore()`, `commands/work-through.md`'s branch/worktree/merge lines and its `:609` `gh pr create` line, `commands/gate-should-we-build.md`'s decisions.jsonl-never-committed line) against each file's real, current text by hand (`grep`/`Read`, no script owns this specific check); then run this repo's own reference/manifest/gate-independence checks against the finished repo state.
Not here:   no new source-file citations beyond what the design doc already lists; no code changes; no PR-body or GitHub-comment writes -- those are `/finish`-time actions (see Not-here follow-ups); markdownlint (`npx -y markdownlint-cli2`) has no repo-relative executable to cite here and isn't a Done-means item -- run it separately as ordinary due diligence.

Done means:
1. [cap]  `scripts/check_references.py` exits 0 against the repo   (tier: script `scripts/check_references.py`)
2. [cap]  `scripts/validate_plugin.py` exits 0 against the repo   (tier: script `scripts/validate_plugin.py`)
3. [hold] `scripts/check_gate_independence.py` exits 0 against the repo   (tier: script `scripts/check_gate_independence.py`)
Evidence: (recorded by `scripts/evidence-capture` once `/build` executes this task; none yet -- this plan has not been built)

## Not-here follow-ups
- Copy the design doc's Success metrics section's merge-time predicate-check
  instruction into the PR body this story's `/finish` opens -- a
  `/finish`-time action; `/build` never opens PRs (this design doc's own
  third bullet). `/handback`'s commit and `/deep-review`'s
  `docs/studious/reviews/metrics.jsonl` append are the two surfaces the
  design doc names as worth spot-checking first.
- Post the PRODUCT.md:193-194 finding as a comment on #255 at merge time
  (the design doc's Out-of-scope durability note) -- the human's action,
  not an executor's; bullet 3 of this same story declares issue/PR writes
  a surface no contract currently governs.
- The ~9 other files restating some version of this invariant, and
  un-parking #247 -- both explicitly out of scope for this story (#255's
  site sweep, and a human's own call on #247, respectively).

---

## Revision History

Signed off via viva review — 1 round, 6 sections, 0 revised. 2026-08-03
