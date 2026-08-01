# Pre-mortem — persona-driven restructure of the delivery flow

- Branch: build/plan-202608010303
- SHA: 7435381
- Date: 2026-07-31

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|----------------|
| 1 | technical | The charter-derived gate-independence check ships after a door rename instead of in the same commit, leaving a window where a renamed judge door (e.g. `commands/review.md`) is off the guarded surface and CI stays green | Mutate a renamed judge door to invoke `/shape` — CI must fail; verify the derivation and the first rename share one commit |
| 2 | technical | The episode ledger's carried/advisory rule demotes a genuine later-round Critical — the waiver path is unimplemented or a judging prompt ignores it — producing a terminal PASS over a known Critical | Episode record showing a Critical tagged `carried` with no waiver entry at a terminal PASS |
| 3 | technical | The PR-time hook and board-ui still read per-gate records after episode records land — the hook reports "audit never ran" on every episode-passing PR, and board retry columns render blank or mislabeled | `gh pr create` on an episode-passing branch (hook must not name missing gates); board render of an episode-tracked story's retry columns |
| 4 | product | `/build`'s surviving name silently widens scope: an operator invoking remembered `/build` gets plan+build with no announcement during the alias window | Window-era build transcripts lack the absorbed-plan-step announcement line |
| 5 | product | Alias creep — the deprecation shims survive past the next major and the door count regresses toward eighteen | README command table exceeds 9 rows after the major that closes the window |
| 6 | product | The bet-less delivery episode's fallback (design doc + PRODUCT.md journeys) goes unimplemented, so `/review --delivery` on an unbetted branch refuses or judges against nothing | Run `--delivery` on a branch with no bet record — the episode report must name its criteria source |
| 7 | technical | The persona charter becomes a second vocabulary source beside DESIGN.md's tables instead of replacing the prose copies — generator 4 reborn under a new name | Door names or roster facts restated outside charter-derived surfaces; two sources disagreeing while CI stays green |
