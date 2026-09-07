### Task 1 — Fix stale docs/doctor lines the judge-fleet epic (#349) left behind [PASS]

Why now:    #349 dispatched gauntlet for every judge lane and split /retro into /health
            and /retro, but five prose spots across the repo still describe the pre-#349
            state or an inaccurate consequence. Canary story of the v4 shakedown epic
            (#351 already landed) — docs-only, cheapest possible run.
Read first: `README.md`, `commands/doctor.md`, `skills/build/SKILL.md`, `skills/ship/SKILL.md`,
            `commands/health.md`, `reference/personas.md`, `commands/review.md`
Rests on:   —
Do:         Fix each finding below so every line reads true against the current repo
            state. Investigate each one yourself against the actual current content —
            don't trust a finding's own guess at specifics (e.g. a claimed count)
            without verifying it first.

            1. README.md — the line saying gauntlet dispatch / /review's changeset lanes
               "follow under #334 S1" is stale; #334 S1 landed. State that plainly,
               present tense.
            2. commands/doctor.md, the agent/skill-registration consequence line
               uniformly claims "/review (or the matching gate) silently runs without
               this lane" for every shipped local agent. False for a local agent no door
               currently dispatches (check every commands/*.md for an actual dispatch of
               each shipped agents/ file — /review and /health's judge lanes are all
               gauntlet:* dispatches, not local files). Name accurately which door(s)
               lose a lane, and say plainly that an unregistered-but-undispatched local
               agent costs nothing today.
            3. commands/doctor.md's `gh` tooling-check consequence line lists "/bet,
               /retro, and the PR-time gate reminder" as depending on `gh`. The
               backlog-hygiene gh read this describes moved from /retro to /health's
               `backlog` mode (#330) — name /health instead.
            4. skills/build/SKILL.md's exorcise section (Step 3): everywhere it names
               the report's "Concepts removed:" line, the report may also carry a
               "Concepts kept:" line — state both. skills/ship/SKILL.md has no rule for
               an exorcise report with no "## Held" section at all (the common case) —
               add one.
            5. commands/health.md's "Save the master summary to
               .../deep-review-summary.md" line names a stale filename (predates the
               /health rename). Rename to match current terminology and fix every other
               reference to the old name (grep the whole repo). Two already-settled
               product decisions to apply verbatim, not open questions: (a) KEEP the
               `codebase (or health)` alias in commands/health.md's area table exactly
               as-is; (b) give /retro its own persona line in reference/personas.md,
               distinct from /health's "Health Officer" row. Update
               tests/python/test_persona_charter.py if it pins the old shared-row shape.

Not here:   No behavior change anywhere — every fix is prose/doc-only. Do not touch
            commands/retro.md's `/retro <area>` handling, do not rename any door, and do
            not add a persona row for anything other than /retro.

Done means:
1. [cap]  README.md's gauntlet-dispatch line and commands/doctor.md's agent-registration consequence line both read true against the current repo   (tier: probe)
2. [cap]  commands/doctor.md's `gh` consequence line names /health, not /retro, for the backlog-hygiene read                                          (tier: probe)
3. [cap]  skills/build/SKILL.md states "Concepts kept:" beside every "Concepts removed:" mention, and skills/ship/SKILL.md rules for a no-"## Held"-section report   (tier: probe)
4. [cap]  commands/health.md's master-summary filename is renamed with no stale reference left, the `codebase (or health)` alias is unchanged, and personas.md gives /retro its own persona line   (tier: probe)
5. [hold] scripts/check_references.py exits 0 and tests/python/test_persona_charter.py still passes, reflecting /retro's new persona row           (tier: test-backed `tests/python/test_persona_charter.py`)

Evidence: grep/read confirmation for each of the five prose fixes; command output for item 5, plus a manual `scripts/check_references.py` run.
