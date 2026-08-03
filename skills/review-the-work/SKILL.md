---
name: review-the-work
description: Use when the user wants something judged — a design vetted before build ("review this design", "is this design sound"), a built branch audited ("audit this", "review this branch", "check this before I merge"), or a finished feature checked against what it promised ("did we ship the right thing", "does this deliver", "acceptance check"). This routes to /review, which picks the matching episode itself. Do NOT use for deciding whether to build at all (that's /bet), for periodic whole-project health sweeps (that's /retro), or for install diagnostics (that's /doctor).
---

# Judge the work

The user wants something reviewed. Route that to the judgment door rather than answering
from the hip.

Invoke the `/review` command. Do not reimplement its logic here and do not pre-select the
episode for it — the command reads repo state and picks: a design doc with no built diff
opens the design episode (**PROCEED TO PLAN / REVISE / RETHINK**), a built diff opens the
work episode (**PASS / FIX AND RE-REVIEW / NEEDS DISCUSSION**). Pass `--delivery` only when
the user explicitly asked about delivery — whether the finished thing delivers what it
promised (**SHIP / FIX AND RE-REVIEW / HOLD**) — because delivery is a boundary someone
decides they have reached, never one inferred from a diff.

Surface the verdict and the findings as the command formats them. The user decides what to
do about them.
