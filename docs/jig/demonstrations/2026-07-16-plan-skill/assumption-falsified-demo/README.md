# DESIGN GAP demonstration -- assumption-falsified (Step 1a)

Closes the acceptance gate's ONE OBSERVATION on story `plan-skill` (fix
cycle, retry after sha `4ac6183`): epic pre-mortem register item #3's
detection hint asked that the assumption-falsified and missing-test-runner
`DESIGN GAP` sub-causes each get their own demonstration, not just the
probe-tooling case `design-gap-demo/` already covers. This folder is the
assumption-falsified leg.

## The fixture claim

`design-doc-falsified-assumption.md` (this folder) proposes a change built
on one factual claim about the real `jig` repo:

> `scripts/plan-lint`'s task-splitting logic, `split_tasks`, already takes
> a `repo_root: Path` second argument alongside `text: str`...

Deliberately false, on purpose, to give Step 1a's code-inventory check
something real to falsify -- not a synthetic stand-in, an actual claim
about this actual repo's actual code.

## Step 1a, run for real against the real repo

Per `skills/plan/SKILL.md` Step 1a: "grep the surface, read the named
files, never trust from the doc's prose."

```
$ grep -n "def split_tasks" scripts/plan-lint
140:def split_tasks(text: str) -> list[tuple[str, str]]:

$ python3 -c "
import ast
tree = ast.parse(open('scripts/plan-lint').read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'split_tasks':
        print('split_tasks params:', [a.arg for a in node.args.args])
"
split_tasks params: ['text']
```

The real signature takes exactly one parameter, `text: str` -- no
`repo_root` parameter exists anywhere on `split_tasks`. The design doc's
claim is falsified.

## Verdict

`/plan`, reading this design doc's Proposed design section, would draft a
checkpoint item against `check_task`'s "already takes `repo_root`" premise.
Step 1a's code-inventory check, run above, finds the real function takes
one argument, not two, and has no `repo_root` parameter to thread through.
Per the design's own resolution ("checked against the real repo... never
trusted from the doc's prose"), `/plan` does not plan around the false
premise or silently correct it -- it stops and reports:

> `DESIGN GAP`: `design-doc-falsified-assumption.md`'s Proposed design
> section claims `scripts/plan-lint`'s `split_tasks` "already takes a
> `repo_root: Path` second argument alongside `text: str`" -- but the real
> function, `scripts/plan-lint:140`, is `def split_tasks(text: str) ->
> list[tuple[str, str]]:`, one parameter, no `repo_root`. Resume action:
> revise the design doc to describe the function's actual signature (and
> decide whether threading `repo_root` through is still part of this
> change's scope), then re-run `/plan`.

This directly answers epic pre-mortem risk #3's detection hint for the
assumption-falsified sub-cause, distinct from `design-gap-demo/`'s
probe-tooling cause and `missing-test-runner-demo/`'s infra cause (this
same fix cycle) -- three distinct messages, three distinct resume actions,
none bare.
