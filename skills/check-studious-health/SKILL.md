---
name: check-studious-health
description: Use when the user asks whether their Studious install is healthy, why a gate seemed to run with fewer checks than expected, whether required tooling (git/gh/jq) is present, or whether context docs (PRODUCT.md/DESIGN.md/CLAUDE.md) are missing or still template stubs — phrasing like "is my studious install healthy", "why did gate-audit skip something", "check my studious setup", "something feels off with studious". Do NOT use for running a specific gate (that's /gate-should-we-build, /gate-design-review, /gate-audit, /gate-acceptance), for periodic project health reviews (/deep-review), for issue triage (/backlog-priorities, /backlog-hygiene), or for initial setup (/studious-init handles first-time scaffolding, not ongoing health checks).
---

# Is Studious healthy?

This is the natural-language entry to `/studious-doctor`. The user is asking whether their install is working correctly, not asking to run a specific gate or review — route that to the doctor command instead of guessing at the answer.

Invoke the `/studious-doctor` command. Do not reimplement its checks here — the command owns them. It reports tooling presence (git/gh/jq), whether every shipped agent and skill actually registered this session, and whether context docs are missing, still template stubs, or populated.

This is read-only and not a gate: there's no verdict to report back, just findings. Surface them as the command formats them.
