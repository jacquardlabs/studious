---
name: continue-feature-work
description: Use when the user wants the next step of feature work already in flight — "do the next piece", "what's the next step on this feature", "continue where we left off", "keep the flow going", or naming an in-progress feature and asking to move it forward. This routes to Studious's /work-on navigator, which runs exactly one step of the gate flow. Do NOT use for picking what to work on across the backlog (that's /backlog-priorities), for evaluating a brand-new idea (that's the should-we-build gate), or for questions about how to implement something — building stays with the user's own workflow.
---

# Do the next piece

The user has a feature mid-flow and wants it moved one step forward without reciting the workflow. Route that to the navigator.

Invoke the `/work-on` command — with no argument to continue the current feature, or with the feature the user named. Do not reimplement its logic here — the command owns position tracking and the step order. It runs exactly one piece (a gate, or a handoff at the design and build steps) and then stops.

One piece per turn. When it finishes, surface its closing position block and wait — never chain into the following step, even if the user seems in a hurry.
