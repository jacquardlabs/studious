# Pre-mortem — Pre-dogfood hardening

- Epic: pre-dogfood-hardening
- Stories: evidence-capture-traversal-fix (#60), subprocess-timeout-process-group-kill (#61), load-bearing-title-match (#62), plan-lint-build-boundary-integration-test (#66)
- Branch: epic/pre-dogfood-hardening
- SHA: befe588
- Date: 2026-07-16

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | `subprocess-timeout-process-group-kill`'s `start_new_session=True` + `os.killpg` assumes a POSIX process-group model (macOS/Linux). If CI or a contributor's environment differs, the fix could silently no-op or raise on an unexpected platform. | Confirm the story's new test actually spawns a backgrounded/piped child and verifies its absence post-timeout on the actual CI platform, not just that no exception was raised. |
| 2 | technical | Four stories land concurrently with no dependency edges; no per-story audit sees the other three stories' diffs together. | The epic finale's own audit fan-out is the only pass that sees the full combined diff — confirm it actually ran against all four merged, not a subset. |
| 3 | product | `load-bearing-title-match`'s new title-matching code path lives only in `tests/_load_bearing.py`, a test-only reference module "never imported by SKILL.md's own procedure" (per #62's own text) — implementing it here doesn't change what the real Foreman does at runtime, only what the test proves is well-defined. | Confirm the story's acceptance criteria and PR description are explicit that this closes the test-proof gap, not a claim that live `/build` sessions now behave differently. |
