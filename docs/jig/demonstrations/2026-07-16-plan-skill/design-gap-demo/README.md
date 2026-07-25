# DESIGN GAP demonstration (issue #13), 2026-07-16

Required demonstration 4 (`docs/design/plan-skill.md`, Operational
readiness): "A design doc proposing a UI-verification task, planned
against a project (real or fixture) confirmed to lack a scripted-probe
tool, produces `DESIGN GAP` naming that specific gap."

`jig` itself has no UI surface (Step 1b's own finding in the design doc),
so per the design's own Open Questions this needed a second, disposable
target-project fixture -- `fixture-repo/`, a minimal Node/Express app with
a `CLAUDE.md`, a `package.json`, and one design doc
(`docs/design/widget-color-picker.md`) proposing a color-picker feature
whose one load-bearing user journey step explicitly requires a
**live-observed** artifact (a real rendered screenshot), not a
DOM-attribute assertion.

## Step 1b, run for real against the fixture

All three checkable signals, cheapest first, actually run (not asserted)
against `fixture-repo/`:

```
$ grep -ni "playwright\|puppeteer\|cypress\|selenium" CLAUDE.md
(no match, exit 1)

$ python3 -c "
import json
pkg = json.load(open('package.json'))
deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
print(sorted(deps.keys()))
"
['express', 'jest']

$ find . -iname "playwright.config.*" -o -iname "cypress.config.*" -o -iname ".puppeteerrc*"
(no output -- none found)
```

One honest wrinkle worth naming: a naive `grep -i playwright` across the
whole `package.json` file *does* match -- the fixture's own `description`
field says "Deliberately carries no playwright/puppeteer/cypress
dependency" in prose, for exactly this reason. Signal (b) is defined as "a
dependency manifest names [the tool]," not "the string appears anywhere in
the file" -- so the real check has to parse `package.json`'s actual
`dependencies`/`devDependencies` keys, not grep the raw file. Written up
here as a real finding for `/plan`'s own eventual implementation to get
right (parse the manifest structurally, don't grep prose), not smoothed
over.

All three signals: **no scripted-probe tool present.**

## Verdict

`/plan`, reading `docs/design/widget-color-picker.md`'s User journey step
3 ("the widget preview re-renders in the new color immediately... a
live-observed artifact... not a DOM-attribute assertion alone"), would
draft that step's checkpoint item as `(tier: probe)` -- the only tier that
honestly represents "the point of the feature is what the user visually
sees change." Step 1b's infra inventory, run above, finds no scripted tool
capable of producing that live-observed artifact headlessly. Per the
design's own three rejected horns (Alternatives considered #4), `/plan`
does not downgrade the item to `test-backed` (a DOM-attribute check the
design doc itself already named and rejected as unable to prove the
browser painted the color), does not write `(tier: probe)` anyway and
defer the gap to `/build` time, and does not fabricate a `judgment` tier.

**`DESIGN GAP`** -- reported the way the Verdicts table requires, naming
the specific cause and one concrete resume action:

> `DESIGN GAP`: `docs/design/widget-color-picker.md`'s User journey step 3
> requires a live-observed verification of the widget's rendered color
> (explicitly rejecting a DOM-attribute-only check in its own Alternatives
> considered section), but `disposable-widget-app` has no scripted-probe
> tool -- `CLAUDE.md` names none, `package.json`'s `dependencies`/
> `devDependencies` name neither `playwright` nor an equivalent, and no
> `playwright.config.*`/`cypress.config.*`/`.puppeteerrc*` file exists
> anywhere in the fixture. Resume action: add a scripted-browser tool
> (Playwright is issue #13's own named example) as its own prerequisite
> piece of infra work, or revise the design to not require live-UI
> verification for this step, then re-run `/plan`.

This is the honest, expected outcome for this specific fixture (it was
built with no probe tool on purpose) -- not a defect in the fixture, and
directly answers epic pre-mortem risk #3 and this story's own "missing
tooling routes to `DESIGN GAP`, never a silent assumption" criterion.
