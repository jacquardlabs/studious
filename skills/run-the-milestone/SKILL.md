---
name: run-the-milestone
description: Use when the user asks Studious to drive an entire milestone or epic autonomously — "knock out this milestone", "run the whole epic", "work through milestone 4", "drive these issues to done as a batch". This routes to Studious's /work-through orchestrator. Do NOT use for a single feature or its next step (that's /work-on via continue-feature-work), for picking what to work on (that's /backlog-priorities), for evaluating one idea (that's the should-we-build gate), or for running a single gate.
---

# Run the milestone

The user wants a whole milestone or epic driven through the gate flow, not one piece
of one feature. Route that to the orchestrator.

Invoke the `/work-through` command — with the milestone, epic issue, or label the user
named, or with no argument to keep driving the epic already in flight. Do not
reimplement its logic here: the command owns plan approval, scheduling, dispatch, and
escalation.

Two things never move out of that command's control: nothing runs before the user
approves the plan, and judgment verdicts (RETHINK, NEEDS DISCUSSION, HOLD) park for
the user rather than retry. When an invocation finishes, surface its closing report
block and wait.
