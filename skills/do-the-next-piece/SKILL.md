---
name: do-the-next-piece
description: Use when the user wants work moved forward without naming a step — "what's next", "do the next piece", "keep going", "where am I on this", "continue", "next" — or wants a whole milestone or epic driven — "knock out this milestone", "run the whole epic", "drive these issues to done". Also use when they ask Studious to start a named issue and carry it — "build issue #12", "take this through the flow". This routes to /next. Do NOT use for picking what to work on (that's /bet), for running a specific review (that's /review), or for a periodic project sweep (that's /retro).
---

# Do the next piece

The user wants work moved forward and hasn't named a step. Route that to the navigator.

Invoke the `/next` command — with no argument to continue what's in flight, or with the
idea, issue, or milestone the user named. Do not reimplement its logic here: the command
owns position tracking, the door order, and the epic-scale dispatch it reads from
`reference/epic-orchestration.md`.

One piece per turn. `/next` reports where the work stands, names the next door, and runs it
on the user's word. When it finishes, surface its closing block and wait — never chain into
the following piece, even if the user seems in a hurry.
