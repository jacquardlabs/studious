# DESIGN GAP demonstration -- missing test runner (Step 1b)

Closes the acceptance gate's ONE OBSERVATION on story `plan-skill` (fix
cycle, retry after sha `4ac6183`): epic pre-mortem register item #3's
detection hint asked that the assumption-falsified and missing-test-runner
`DESIGN GAP` sub-causes each get their own demonstration, not just the
probe-tooling case `design-gap-demo/` already covers. This folder is the
missing-test-runner leg.

`fixture-repo/` is a minimal, disposable Python target-project fixture:
one script (`format_report.py`), a `CLAUDE.md` naming no baseline/test
command anywhere, and one design doc
(`docs/design/csv-column-alignment.md`) whose one load-bearing checkpoint
item needs a `test-backed` verification tier -- a pure function, no UI
surface, so `test-backed` (not `probe`) is the honestly-correct tier to
propose; the gap here is that no test runner exists to back it with.

## Step 1b, run for real against the fixture

`skills/plan/SKILL.md` Step 1b: "Read the target project's own `CLAUDE.md`
for its stated baseline/test command... never guess a test runner and
never hardcode one."

```
$ grep -ni "test\|baseline\|pytest\|unittest\|jest\|npm test" CLAUDE.md
4:fix cycle's missing-test-runner `DESIGN GAP` demonstration (acceptance
12:No "Tests" row, no baseline/test command, and no linter named anywhere in
14:demonstration: Step 1b's test-runner read ("read the target project's own
15:`CLAUDE.md` for its stated baseline/test command... never guess a test
```

The same honest wrinkle `design-gap-demo/README.md` already flagged for
its own probe-tooling grep, reproduced here for the test-runner signal: a
naive `grep -i test` false-positives on the fixture's own disclaimer prose
(which discusses "test" and "baseline" by name, precisely because it's
explaining the omission). The real check has to look for the structured
shape this repo's own `CLAUDE.md` files actually use -- a `### Quality
gates` section with a `**Tests**` bullet -- not grep raw prose for the
word:

```
$ grep -n "^#\+ Quality gates\|\*\*Tests\*\*" CLAUDE.md
(no output -- none found, exit 1)
```

No stated baseline/test command anywhere in the fixture's `CLAUDE.md`.

## Verdict

`/plan`, reading `docs/design/csv-column-alignment.md`'s User journey step
3, would draft that step's checkpoint item as `(tier: test-backed)` -- the
correct, honestly-representative tier for a pure function with no UI
surface (unlike `design-gap-demo/`'s probe case, this is not a tooling
question the human needs to install something for -- it is Step 1b's
*other* named infra check, "test runner," coming up empty). Step 1b's
infra inventory, run above, finds no stated baseline/test command in the
target project's `CLAUDE.md`. Per the Verdicts table's second `DESIGN GAP`
cause ("Step 1b finds required infra -- test runner... -- missing and
uncreatable by an earlier task"), `/plan` does not guess a test runner
(`pytest`? `npm test`? nothing in this fixture says so), does not silently
downgrade the item to an unverified claim, and does not write the
checkpoint item anyway and defer the gap to `/build` time. It stops and
reports:

> `DESIGN GAP`: `docs/design/csv-column-alignment.md`'s User journey step 3
> needs a `test-backed` checkpoint item (a pure function, no UI surface),
> but `disposable-report-formatter`'s `CLAUDE.md` states no baseline/test
> command anywhere -- no `### Quality gates` section, no `**Tests**`
> bullet, nothing `/plan` can read the way `/build`'s own Step 1 already
> reads one. Resume action: add a `### Quality gates` section naming the
> project's actual test command (e.g. `pytest`, once a suite exists) to
> `CLAUDE.md` as its own prerequisite piece of infra work, then re-run
> `/plan`.

This directly answers epic pre-mortem risk #3's detection hint for the
missing-test-runner sub-cause, distinct from `design-gap-demo/`'s
probe-tooling cause and `assumption-falsified-demo/`'s falsified-claim
cause (this same fix cycle) -- three distinct messages, three distinct
resume actions, none bare.
