# Pre-mortem — Epic-driven audit path first-round changeset routing

- Design doc: docs/superpowers/specs/2026-07-15-audit-first-round-routing-design.md
- Branch: worktree-cut-down-on-token-usage
- SHA: 0bef3b6
- Date: 2026-07-15

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|----------------|
| 1 | technical | The mechanical routing dispatch dies/times out, but the fail-closed fallback (`routed = AUDITORS`) has a wiring bug and doesn't actually trigger | Fixture-test a dead/malformed dispatch response and confirm all 9 lanes still dispatch |
| 2 | technical | `resolveAuditRoster`'s flag-to-lane mapping is inverted in implementation (e.g. `frontendMatch` accidentally gates the infra lane) | Unit test each match flag independently and confirm it routes only its own lane |
| 3 | technical | `auditFanIn`'s `laneNames` isn't actually switched from `AUDITORS.map(...)` to `routed.map(...)`, silently letting a compiling agent name a routed-out lane in `blockingLanes` | Diff `auditFanIn`'s lane-list construction in the implementation PR |
| 4 | product | The compiled Summary's routed-out lines get merged, truncated, or dropped when multiple lanes route out at once, leaving the user still uncertain how many lanes actually ran | Run a case with all 3 routable lanes routed out and confirm each appears as its own distinct line |
| 5 | product | The "routed out" vs "…skipped" vocabulary mismatch between `/work-through`'s Summary and standalone `/gate-audit`'s skip notes ships unaddressed, reading as two different outcomes for the same thing | Compare the rendered wording in both surfaces' output for the same skip condition |
| 6 | technical | Relocating the pattern lists into `reference/audit-routing-signals.md` drops or alters an entry from `gate-audit.md`'s original prose during the edit (copy-paste omission) | Diff auditor 9 and 6–8's old inline prose against the new reference file for exact pattern parity |
| 7 | technical | The mechanical dispatch recomputes every round with no cap, and on a high-concurrency multi-story epic the added dispatch volume isn't reflected in the cost table's projected savings | Compare the issue's projected dispatch count against an actual multi-story epic run's dispatch count |
