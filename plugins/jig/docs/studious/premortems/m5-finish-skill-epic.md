# Pre-mortem — M5: /finish skill

- Epic: m5-finish-skill
- Stories: finish-skill (#20)
- Branch: epic/m5-finish-skill
- SHA: ef95db6
- Date: 2026-07-12

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | `/finish`'s "freshness hold: evidence timestamp >= last code commit" is the same ordering-assumption class of bug #44 just found in `verify` — a producing step that commits *after* writing the artifact it's timestamping against makes the check structurally unpassable. | Confirm `/finish`'s freshness check compares evidence timestamps against a floor that's provably before the evidence is written, not the branch's own final commit — and that this was checked explicitly against #44's finding, not assumed clear. |
| 2 | technical | The cctx footer step depends on cctx being installed. A naive implementation could error when it's absent, or silently omit the footer without telling the user — either violates PRODUCT.md's "Standalone-capable" principle (every degradation graceful, none silent). | Run `/finish` without cctx installed and confirm it says explicitly it's skipping the footer, rather than erroring or silently omitting it. |
| 3 | process | Steps 3/4 (file survivors as issues, propose decision patches) must stay "propose; never apply" per jig's own principle and `/work-through`'s own read-only-GitHub posture. A less careful implementation could auto-file issues or auto-commit doc patches. | Confirm `SKILL.md` explicitly gates issue-filing and doc-patch application behind an explicit user confirmation step, and no code path calls `gh issue create` or writes to PRODUCT.md/DESIGN.md/CLAUDE.md without one. |
| 4 | technical | The four cleanup verdicts (MERGE/PR/KEEP/DISCARD) have different worktree/branch lifecycle implications. A build/demo that only exercises one verdict path (most likely MERGE) risks leaving the other three under-specified or broken. | Confirm the story's acceptance evidence demonstrates or unit-tests all four verdict branches' cleanup behavior, not just one happy path. |
