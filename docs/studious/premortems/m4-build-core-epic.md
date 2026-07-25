# Pre-mortem — M4: /build core loop

- Epic: m4-build-core
- Stories: build-scripts (#14 scripts), build-skill (#14 skill)
- Branch: epic/m4-build-core
- SHA: 8be8cce
- Date: 2026-07-12

| # | Lane | Failure mode | Detection hint |
|---|------|--------------|-----------------|
| 1 | technical | This is the first jig skill ever actually *invoked* end-to-end — M0's dogfood hand-simulated /design, it never ran a real skill file. The SKILL.md prose could read correctly but diverge from real behavior once Claude Code actually dispatches fresh-executor subagents via the Task tool. A spec that was never exercised live is unverified, not proven. | Check for evidence of a live invocation — a real `/build` run against a real PLAN.md, not just a written spec. Evidence artifacts under `docs/jig/evidence/` or an equivalent transcript should exist and show an actual dispatched executor, not a described one. |
| 2 | technical | Fresh-executor isolation ("exactly the task block + Read-first + discipline skill, not other tasks' history") is a strong claim. A naive dispatch implementation could leak the calling session's broader context (the plan, prior tasks, the design doc) into the executor's prompt, silently violating the isolation the whole architecture depends on. | Inspect the actual dispatch prompt built for an executor (in the SKILL.md's own instructions, or a captured real dispatch) and confirm it contains only the task block, its named Read-first pointers' content, and the task-execution-discipline skill — nothing else from the surrounding session. |
| 3 | technical | `build-skill` depends on `build-scripts`, but issue #14's original text assumed `/plan`/`plan-lint` exist (its own "Rests on" line named #11). This epic deliberately unblocks via a hand-written PLAN.md instead — risk the skill's prose still references scripts, conventions, or a plan-lint pass that were never actually built in this scoped pass. | Grep `skills/build/SKILL.md` for any reference to `/plan`, `plan-lint`, or an assumed PLAN.md-generation step, and confirm each either doesn't exist or is explicitly framed as "if invoked after /plan" rather than a hard requirement. |
| 4 | technical | Removing the inspector (#15) from this pass — rather than stubbing it — could leave the SKILL.md with a dangling reference to an "inspect (load-bearing only)" step that doesn't exist yet, breaking the workflow's own described sequence. | Confirm the SKILL.md's inspection step is an explicit no-op/stub with a comment pointing at #15, not a silently-omitted step or a broken reference to code that isn't there. |
