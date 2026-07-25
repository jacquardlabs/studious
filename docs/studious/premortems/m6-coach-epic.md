# Pre-mortem — M6 — Coach

- Epic: m6-coach
- Stories: coach-skill (#21)
- Branch: epic/m6-coach
- SHA: 31543d9
- Date: 2026-07-17

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | Contract drift against the real skills: handoff §5.5 predates M2–M5, so the four skills' actual entry conventions (what `/plan` accepts, `/design` revision mode's `--prior-input`/`--prior-verdicts` resume, `/build`'s PLAN.md path) may differ from what §5.5 assumes. A coach that passes what the handoff said instead of what the skills accept dispatches them wrong. | Confirm the coach's dispatch instructions were written against each landed `SKILL.md`'s actual invocation contract, not the handoff text — spot-check `/design` revision mode and `/plan` handoff against `skills/design/SKILL.md` and `skills/plan/SKILL.md`. |
| 2 | process | Pocock-rule erosion: implementation drifts into auto-chaining user-invoked skills or doing work itself — the resident-coordinator failure PRODUCT.md's "What we're NOT building" rules out. | Confirm `SKILL.md` gates every dispatch behind explicit human confirmation and no path dispatches a second skill from one confirmation; confirm the coach writes no code, flips no statuses, records no verdicts. |
| 3 | technical | Vocabulary mismatch: the coach reads `BUILT`/`PAUSED`/`ESCALATED`, task-status `PASS`, and studious gate verdicts. Jig's task-level `PASS` and studious's gate-level `PASS` are different concepts sharing a word (DESIGN.md risk #2) — a misread misroutes the recommendation. | Confirm the coach's state-reading distinguishes task-status `PASS` (PLAN.md status lines) from gate-verdict `PASS` (studious ledger), and its routing names the exact tokens each skill actually emits per DESIGN.md's Vocabulary table. |
| 4 | technical | State misread on real repos: status lines are flipped by scripts only, and repo evidence must outrank conversational claims. A coach that parses PLAN.md loosely or trusts the conversation recommends the wrong next step. | Confirm assessment is demonstrated against ≥3 distinct real repo states, including at least one where the repo contradicts what the conversation claims and the repo wins. |
| 5 | technical | Invocation-convention dead end: the convention chosen at design time (own slash command vs. another mechanism — DESIGN.md risk #4) conflicts with Claude Code's user-invoked/model-invoked skill semantics, leaving the coach uninvokable or auto-triggering. | Confirm the shipped frontmatter matches the design decision and a live invocation of the chosen form actually reaches coach behavior — the stub's "do not invoke" description must be gone. |
| 6 | process | Silent degradation: the coach recommends studious gates (`/gate-design-review`, `/gate-audit`, `/gate-acceptance`) on a standalone install without naming the gap, violating the Standalone-capable principle (every degradation graceful, none silent). | Exercise or walk the no-studious path and confirm the recommendation explicitly names what's skipped and why, rather than erroring or silently omitting the gate step. |
