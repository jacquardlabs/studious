# Design: acceptance-dispatch-fix

## Problem & persona

**Consumer:** the human deciding to fund the work; product-reviewer Q1.

Studious's primary persona (PRODUCT.md: "a developer... who wants product judgment and quality gates woven into the build, without heavy process") and its secondary persona (the maintainer dogfooding Studious on Studious) both drive epics through `/work-through`. Today, a story whose design-review persisted a per-story pre-mortem register can hit an acceptance `HOLD` that has nothing to do with the code under review — the epic-driven acceptance dispatch (`workflows/epic-driver.js`'s `acceptanceRound`, lines ~219–326) never runs the pre-mortem verification step `commands/gate-acceptance.md` Part 2 already specifies, and its mechanical changeset scan can silently hand the product-reviewer an empty file list.

- **Bug 1** — `acceptanceRound`'s code comment (lines 225–227) asserts "no per-story register exists to verify." False whenever `gate-design-review` Part 4 persists one (`docs/studious/premortems/<design-doc-slug>.md`) — which it does for any story whose design review found risks worth registering. The visible symptom is an avoidable `HOLD`, but that's the *lucky* outcome: nothing today structurally stops the acceptance compiler from certifying `SHIP` with the register never verified at all. `HOLD` only happened in the incident that surfaced this bug because the opus compile agent independently noticed, while reading `gate-acceptance.md` on its own initiative, that a required lane was missing — not because anything forced it to check. A less careful compile pass would have shipped a story with an unverified pre-mortem register and no one would know.
- **Bug 2** — the mechanical scope-check (`acceptanceScopeCheckPrompt`, dispatched at `haiku`/`effort: low`) can return an empty `files` array that `acceptanceRound` trusts at face value (line 289 only guards `null`, not `[]`) and passes straight to the product-reviewer. Reproduced by hand on `epic/finale-gate-overlap--overlap-acceptance-audit`: the underlying `git merge-base` / `git diff --name-only` commands return the correct 4-file changeset when run directly — this is a flaky cheap-agent execution issue, not a git-logic bug.

Without this fix: any epic-driven story with a per-story register can reach `SHIP` with that register never actually verified — a silent quality escape, not a hard block on reaching `SHIP` — and a rare scope-check flake can silently degrade review quality the same way, neither one surfacing as a gap unless a compile agent happens to notice on its own.

## Proposed design

**Consumer:** product-reviewer Q2/Q6; `/plan`'s spine-building step.

Two independent, additive fixes inside `acceptanceRound`, leaning on PRODUCT.md's "code owns bookkeeping" and "evidence over invention" principles — no new product surface, no change to verdict tokens or gate vocabulary.

- **Bug 1 fix** — `acceptanceRound` gains a Part-2-equivalent step: after the scope-check resolves the changeset `files` list, scan it for `docs/studious/premortems/*.md`, mirroring `gate-acceptance.md` Part 2's discovery order — changeset-scan first, fallback to the most-recently-modified file under that directory, a fallback candidate counting only if its `Branch:` header matches the current branch. The fallback lookup is held to the same fail-closed standard as Bug 2's guard below: if it can't confirm with confidence that no register exists — its own dispatch dies, or returns an ambiguous result — the lane degrades to `UNREVIEWED` rather than being treated as a confirmed absence. Without this, a flaked fallback lookup would reintroduce Bug 1's exact silent-`SHIP` escape through a second path Bug 2's own guard doesn't cover. One deliberate divergence from Part 2, not a verbatim port: Part 2's own disambiguation step ("if there are several candidates, ask the user which one") has no automated equivalent inside a non-interactive fan-out. When the `Branch:`-header filter still leaves more than one candidate — whether the changeset itself names more than one register file, or the directory-scan fallback does — the lane degrades to `UNREVIEWED` instead of guessing, the same fail-closed rule Bug 2's fix uses below. If exactly one register resolves, dispatch `@agent-premortem-auditor` (lane `product`) against it *inside the existing `parallel()` batch alongside product-review and walkthrough* — not a serial addition after it, which would reintroduce the per-dispatch latency issue 219–224's code comment (issue #142) already fixed once for this function. Feed its `REALIZED` findings into `acceptanceFanIn`'s compile prompt as a third input block, mapped by the same `BLOCKER`/`SHOULD FIX` vocabulary Part 4 already uses. Evidence-log parity with the interactive command's Part 0 is deliberately deferred — see Out of scope.
- **Bug 2 fix** — extend the existing fail-closed guard. `acceptanceRound` already treats a died scope-check agent (`scope === null`) as `UNREVIEWED` via the `missing.push(...)` path (lines 301–315). Treat an empty-but-non-null `files` array the same way: skip the product-review dispatch, mark that lane `UNREVIEWED`, and let the existing missing-lane logic cap the verdict at `HOLD` — no separate retry mechanism.

Every `UNREVIEWED` cause carries its own distinguishable reason in the compiled summary — a died dispatch, an empty-but-suspicious changeset (Bug 2), an unresolved multi-candidate register, or a failed fallback lookup are four different situations with four different remedies (retry vs. manually disambiguate vs. investigate), not one generic "agent died" string a maintainer has to guess the real cause behind.

From the user's side (the maintainer watching `/work-through`'s "Needs you" queue): a story with a real per-story register now gets its items actually verified before a verdict is certified, and a transient scope-check flake reads as an explicit, specific `UNREVIEWED` finding instead of an invisible empty-scope review.

## User journey

**Consumer:** product-reviewer Q3; `/plan`'s task-boundary decisions.

Extends PRODUCT.md's critical user journey #2 (per-feature gate flow), at the epic-driven altitude:

1. A story's design-review finds risks worth registering, persists them per `gate-design-review` Part 4, returns `PROCEED TO PLAN`.
2. Build lands; `/gate-audit` runs (unaffected by this fix — audit's own pre-mortem carve-out at `epic-driver.js` line 544 is a separate, correct exclusion for the epic-level register, not touched here).
3. `epic-driver.js` dispatches the story's acceptance round. **Changed step:** the round now discovers the per-story register, dispatches `premortem-auditor`, and folds its verdict into compilation alongside product-review and the walkthrough.
4. Compilation reaches `SHIP` when nothing is `UNREVIEWED` and no lane raised a `BLOCKER`/unresolved `SHOULD FIX` — including the (now-verified) register.
5. The story lands on the epic branch. No change to any later step.

Nothing in this journey changes for a story with **no** per-story register — the new step is conditional on one existing, matching Part 2's own "runs only when a register exists" framing.

**Failure path.** If the register-discovery scan *confirms* no matching file (changeset names none, and the `Branch:`-matching fallback confirms none exists), the step is skipped entirely — same as today, correctly. If a register *is* discovered but the `premortem-auditor` dispatch dies, the scope-check itself returns an empty-but-suspicious file list (Bug 2), more than one candidate register survives the `Branch:`-header filter with no automated way to pick one, or the fallback lookup can't confirm absence with confidence, that lane is marked `UNREVIEWED` — with a cause-specific reason, not a generic one — via the existing missing-lane guard, and the verdict caps at `HOLD`; it never silently degrades to `SHIP`. A story never ships on an unreviewed register or an unreviewed changeset, whichever bug or ambiguity would otherwise have caused it — and "no register found" only ever means a confirmed absence, never an unconfirmed one.

## Out of scope

**Consumer:** product-reviewer Q4.

- The epic-level cross-story pre-mortem register, verified once at the epic finale — untouched; that dispatch (`premortemDispatchPrompt`, lines 213–217) and its own discard-and-redo logic are a separate, already-correct mechanism.
- Audit's pre-mortem carve-out (the compile prompt's explicit "disregard that lane here" instruction at line 544) — a different gate, a different register, correctly excluded already.
- The interactive `commands/gate-acceptance.md` command itself — its Part 0 changeset resolution runs directly via Bash inside the orchestrating agent, with no separate cheap sub-dispatch to flake, so it has no equivalent of Bug 2 to guard against.
- A retry mechanism for the scope-check dispatch — the fix fails closed (`UNREVIEWED`) rather than adding a second attempt at a different model tier.
- Any change to gate verdict tokens, `GATES` config, `MAX_FIX_CYCLES`, or `gate-ledger`'s schema.
- Re-verifying the currently-parked `finale-gate-overlap--overlap-acceptance-audit` story as part of this work — it resolves itself on the next `/work-through` invocation once this fix is released (see Operational readiness).
- Wiring the branch's evidence log (`gate-ledger evidence-list --dedupe`) into the new premortem-auditor dispatch, matching the interactive command's Part 0. Deliberately deferred: `acceptanceRound` has no equivalent resolution step today, so this would be a net-new addition, not a stamp-in, and the block isn't load-bearing for either named bug — it only upgrades `premortem-auditor`'s "CAN'T VERIFY" language to an attested citation. Leaves one small, tracked gap between the epic-driven and interactive acceptance paths on this attestation detail; a candidate for a future story if it proves to matter in practice.

## Alternatives considered

**Consumer:** product-reviewer Q5; future readers reconsidering a rejected path.

- **Bug 1 discovery mechanism** — **(recommended): A.** (A) Reuse `gate-acceptance.md` Part 2's existing changeset-scan + fallback + `Branch:`-header contract, with one deliberate divergence for the non-interactive fan-out: an unresolved multi-candidate match degrades to `UNREVIEWED` instead of Part 2's interactive "ask the user." (B) Add a new `work-set --premortem-doc <path>` ledger field, written by `gate-design-review`, read directly by acceptance. Rejected: (B) adds ledger schema surface and a second source of truth that can drift from the file's actual state; (A) is the contract that already exists and needs zero schema change beyond the one automation-forced fail-closed rule — reuse over creation.
- **Prompt-builder sharing** — **(recommended): A.** (A) A new, separate prompt-builder tailored to Part 2's discovery logic. (B) Refactor the finale's `premortemDispatchPrompt` into one shared helper parameterized for both call sites. Rejected: (B) — the finale always knows its register path (`epic.premortem`, no discovery needed) while the per-story case discovers a path via scan+fallback+header-check; forcing one abstraction over genuinely different semantics is the premature abstraction CLAUDE.md warns against. Three similar lines beat a shared parameter that has to branch internally on "am I the finale or a story."
- **Evidence-log parity** — **(recommended): B.** (A) Full parity with Part 2, including the evidence-log block. (B) Core premortem dispatch only, evidence-log wiring deferred. Corrected from an earlier round of this doc, which rejected (B) on a false premise (that the block was "already resolved" in `acceptanceRound` and needed only stamping in) — `acceptanceRound` has no Part-0-equivalent resolution step at all; full parity would be a genuinely new addition, not a stamp-in. Rejected: (A) — the evidence-log block isn't load-bearing for either named bug (it only upgrades `premortem-auditor`'s "CAN'T VERIFY" language to an attested citation), so adding a net-new resolution step to close it is scope beyond what the two bugs require. (B) keeps the fix tight; the resulting interactive-vs-epic-driven gap on this one attestation detail is deliberately accepted, tracked in Out of scope.
- **Bug 2 guard shape** — **(recommended): A.** (A) Treat an empty `files` array identically to a died agent — degrade to `UNREVIEWED` via the existing pattern. (B) Retry once at a higher model/effort tier before giving up. Rejected: (B) — adds cost, latency, and a second partial-failure mode for what looks like a rare flake; the existing fail-closed pattern already has a well-understood, tested shape.
- **Fix scope** — **(recommended): A.** (A) Confine both fixes to `epic-driver.js`'s `acceptanceRound`. (B) Also add a defensive empty-changeset guard to the interactive `gate-acceptance.md` Part 0, as a precaution. Rejected: (B) — Part 0 has no separate cheap sub-dispatch to flake; adding a guard against a failure mode that structurally can't occur there is validating a scenario that can't happen (CLAUDE.md).

## Operational readiness

**Consumer:** `/gate-audit`'s operability lane; `/build`'s rollout-tier verification.

- **Migration** — none. Pure control-flow addition inside one function; no data or schema change.
- **Rollback** — a plain `git revert` of the merge commit; no state to unwind.
- **Rollout / deployment gap** — the running driver is the *installed* plugin copy (`~/.claude/plugins/cache/.../studious/<version>/workflows/epic-driver.js`), not this repo's source. This fix has no effect on any `/work-through` run — including re-verifying the currently-parked `overlap-acceptance-audit` story — until it merges, releases, and the installed plugin version bumps. That parked story does not need special re-verification handling (per the interview): acceptance is stateless per-invocation, so a plain `/work-through` re-run after the new version installs exercises the fixed code automatically.
- **Working/failing signal** — `gate-ledger gate-get`'s recorded `acceptance` verdict and summary. Working: a story with a real register shows a premortem-auditor contribution in the compiled summary instead of the register going unmentioned. Failing: the scope-check guard's new `UNREVIEWED` path should be visible in the compiled summary's `missing` list, distinguishable from today's silent empty-array pass-through.
- **Verification of this fix itself** — this story's own acceptance gate would hit the identical unfixed bugs if driven through the (still-old) installed `epic-driver.js`. Verify manually via `/gate-acceptance`'s interactive path instead of the epic-driven fan-out for this story specifically.

## Open questions

**Consumer:** the human sponsor; the next `/design` revision round.

- Should `gate-design-review` Part 4's register-writing step also note, in its own output, whether the interactive `/gate-acceptance` command's Part 2 language needs any wording update once this fix lands — or does "the epic-driven path now matches Part 2" require no doc changes at all since Part 2 was already the correct spec? (Leaning: no doc change needed — Part 2 was already right; only `epic-driver.js` was out of sync with it.)
- Once released, is there a cheap way to confirm in production that the premortem-auditor dispatch actually fired for a real story (beyond reading one gate-ledger summary by hand) — e.g., a `/review-outcomes`-style check across future epic runs? Left for a follow-up, not this fix.

---

## Revision History

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-23

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-23

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-23

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-23

Signed off via viva review — 1 round, 8 sections, 0 revised. 2026-07-23
