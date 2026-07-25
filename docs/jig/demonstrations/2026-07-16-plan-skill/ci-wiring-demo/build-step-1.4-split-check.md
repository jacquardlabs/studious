# /build Step 1.4 split-logic check against this real PLAN.md

Required demonstration 2 (`docs/design/plan-skill.md`, Operational
readiness): "Run the real `PLAN READY` `PLAN.md` from (1) through
`/build`'s actual Step 1.4 split logic... and confirm the split matches
`/plan`'s own intended task boundaries."

`skills/build/SKILL.md`'s own Step 1.4 is explicit that this is **the
Foreman's own judgment, not a mechanical heading-depth parser**: "read to
each `### Task N — <title>` heading and stop accumulating a task's content
at the next `### ` heading. Explicitly exclude any trailing content at a
coarser heading level... from the last task's block." A fresh `/build`
session applies that reading rule by hand; there is no separate script to
invoke. The check below reproduces that exact rule mechanically (the same
regex pair `scripts/plan-lint`'s own `split_tasks()` already encodes for
the identical purpose, per that script's own docstring: "matching
`/build`'s own Step 1.4 rule verbatim") so the result is checkable, not
just narrated.

```python
import re
text = open("PLAN.md").read()
TASK_HEADING_RE = re.compile(r"^### Task (\d+)\b.*$", re.MULTILINE)
HEADING_LEVEL_1_TO_3_RE = re.compile(r"^(#{1,3})[ \t]", re.MULTILINE)
task_matches = list(TASK_HEADING_RE.finditer(text))
boundary_starts = sorted(h.start() for h in HEADING_LEVEL_1_TO_3_RE.finditer(text))
for m in task_matches:
    start = m.start()
    end = next((b for b in boundary_starts if b > start), len(text))
    print(m.group(1), len(text[start:end]), "chars")
```

Real output against `ci-wiring-demo/PLAN.md`:

```
=== Task 1 block: 1573 chars ===
### Task 1 — Add `.github/workflows/ci.yml`'s `test` job | Why now: ...
... ends with: 'cutes this task; none yet -- this plan has not been built)\n\n'

=== Task 2 block: 1719 chars ===
### Task 2 — Add the `lint` job (Ruff + both plan-lint fixtures) to `.github/wor...
... ends with: 'cutes this task; none yet -- this plan has not been built)\n\n'

=== Task 3 block: 1164 chars ===
### Task 3 — Update `CLAUDE.md`'s Linter row to drop the "not yet wired into a C...
... ends with: 'cutes this task; none yet -- this plan has not been built)\n\n'
```

Three task blocks, exactly the three `/plan` drafted, each stopping cleanly
before the next `### Task` heading and — for Task 3 — before the trailing
`## Not-here follow-ups` section (confirmed: no block's tail includes the
`## Not-here follow-ups` text; the viva round-trip evidence in
`viva-round-trip/` confirms the same boundary independently, from the
reviewer-facing side). The split `/build`'s Step 1.4 rule produces matches
`/plan`'s own intended task boundaries exactly.
