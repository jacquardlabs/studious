# Pre-mortem — acceptance-dispatch-fix

- Branch: worktree-groupB
- SHA: 23babba
- Date: 2026-07-23

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | Build could reuse the exact same "agent died" string for all four `UNREVIEWED` causes instead of the cause-specific text the design requires — verdict-capping still works, but the mental-model benefit is lost | Grep the merged diff's missing-lane guard for distinct summary text per cause, not one shared literal |
| 2 | technical | The fallback-discovery dispatch's own model/effort tier is unspecified; if built cheaply (mirroring Bug 2's own flaky `haiku`/`low` scope-check), the fail-closed guard mitigates the symptom but not the frequency — could make `UNREVIEWED`→`HOLD` common enough to be a real usability regression despite being structurally safe | Check the fallback dispatch's assigned model/effort in the build diff; watch real `HOLD` frequency on registered stories in the first few epics after release |
| 3 | product | Four distinguishable `UNREVIEWED` causes add real cognitive surface to the "Needs you" queue vs. today's one generic `HOLD` — a net improvement, but risks violating the terse one-token-one-sentence queue format if each cause's explanation runs long | Check a real post-build `HOLD` entry in the "Needs you" queue against `reference/gate-vocabulary.md`'s formatting convention |
| 4 | technical | `acceptanceFanIn`'s compile prompt (pinned `opus`) gains a third input block; token/latency impact on the compile step itself is unmeasured, likely negligible but unverified | Compare `acceptance:compile` dispatch token usage on a registered vs. unregistered story post-build |
| 5 | product | Design is grounded in one real incident's exact register shape (7 items, 2 product-tagged); a register with zero product-lane items still requires dispatching `premortem-auditor` per Part 2's own spec — an implementation could wrongly skip dispatch on a "nothing to check" assumption | Verify with a register containing only technical-lane items that `premortem-auditor` (lane `product`) is still dispatched, not skipped |
