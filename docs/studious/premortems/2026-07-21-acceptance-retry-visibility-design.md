# Pre-mortem — Surface silent gate-acceptance dispatch retries via per-phase durations

- Design doc: docs/superpowers/specs/2026-07-21-acceptance-retry-visibility-design.md
- Branch: epic/perf-audit-followups--acceptance-retry-visibility
- SHA: ca514d4
- Date: 2026-07-21

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|----------------|
| 1 | technical | The per-story `work-get` read added to the reporting step aborts the whole report block on one missing/corrupt work file instead of skipping just that story | Feed a report run one unreadable/malformed work file and confirm the other stories still render; grep the edit for a per-story best-effort skip, not a single jq that aborts on first bad file |
| 2 | technical | First-phase duration uses the work file's `createdAt` as predecessor; a pre-existing or hand-edited file missing `createdAt` renders a literal NaN/negative first delta | Run the computation against a work file with no `createdAt`; confirm the first phase shows no duration rather than "NaN"/a negative number |
| 3 | technical | The delta arithmetic ships as `jq`/prose in `commands/work-through.md` instead of a `gate-ledger` verb, so timestamp math lives outside code with no `tests/test_gate_ledger.sh` coverage — acceptable only while single-consumer | If deferred `finaleGate` duration surfacing later lands (a second consumer), confirm the computation was promoted to a verb, not copy-pasted into a second prose site |
| 4 | technical | History is rendered "in place of" the driver's collapsed `trail`; if the build drops `trail` and the history read then fails, the report loses the verdict trail it shows today (a regression) | Confirm the edit falls back to the driver's own `trail` string when a story's history can't be read or computed, rather than rendering nothing |
| 5 | product | `work-get`'s `history` is cumulative across runs, but the report frames stories as "this run" — a resumed story would surface prior-run phases too | Run a resumed-story case and confirm the rendered phase list either scopes to this run or intentionally accepts full history, matching the doc's stated intent |
| 6 | product | The duration is un-attributed: a genuinely long-but-healthy gate and a silently-retried one render identically, so a persona could misread a legitimately slow gate as a stall | Confirm the report text stays fact-only (no "stalled"/"slow"/"retried" adjective) so the number invites, never asserts, investigation — the criterion-4 guarantee |
| 7 | product | Durations render on every phase of every reported story, adding visual weight to the common healthy case and cutting against "lightweight and optional" | Eyeball a normal multi-story landed report; the annotation should be a compact parenthetical inline with the trail, not a separate per-story table |
