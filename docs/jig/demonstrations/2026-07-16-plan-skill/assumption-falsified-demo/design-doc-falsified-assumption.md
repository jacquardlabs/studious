# Design: add a `repo_root`-aware task filter to `scripts/plan-lint`

Fixture design doc, written solely to host this fix cycle's assumption-
falsified demonstration (acceptance gate's ONE OBSERVATION on story
`plan-skill`: pre-mortem register item #3's detection hint, "verify the
assumption-falsified and missing-test-runner causes are demonstrated, not
only the probe case demo 4 covers"). Not a real feature -- the codebase
claim below is deliberately wrong, on purpose, to give Step 1a something
real to falsify.

## Problem & persona

`scripts/plan-lint`'s task-splitting logic, `split_tasks`, already takes a
`repo_root: Path` second argument alongside `text: str`, which callers use
to resolve `Read-first` paths relative to the target repo. A new task
category filter needs to consult `repo_root` too, so it can be added as a
third positional parameter without changing `split_tasks`'s own signature.

## Proposed design

Add a `category` keyword parameter to `check_task` that consults the
`repo_root` value `split_tasks` already threads through, filtering tasks
whose `Read-first` line resolves outside `repo_root`.

## User journey

N/A -- an internal linter change, no user-facing surface.

## Out of scope

Any change to `main`'s CLI argument parsing.

## Alternatives considered

N/A -- fixture doc, single approach.

## Operational readiness

A pure internal refactor to one script; no migration, no deployed service.

## Open questions

None.
