# Design: add a color picker to the widget settings panel

Fixture design doc, written solely to host this story's DESIGN GAP
demonstration (`docs/design/plan-skill.md`, Operational readiness,
demonstration 4). Not a real feature.

## Problem & persona

A user of `disposable-widget-app`'s settings panel can only change the
widget's color by editing a config file by hand today; there's no in-app
control.

## Proposed design

Add a color-swatch picker to the settings panel's existing form. Clicking
a swatch updates the widget's rendered color live, without a page reload.

## User journey

1. User opens the settings panel.
2. User clicks a color swatch.
3. The widget preview re-renders in the new color immediately -- this is
   the load-bearing, user-facing behavior a checkpoint item must verify
   with a **live-observed** artifact (a real rendered screenshot showing
   the new color applied), not a DOM-attribute assertion alone: the point
   of the feature is what the user visually sees change, and a unit test
   asserting `element.style.color === '#ff0000'` would pass even if a CSS
   rule elsewhere silently overrode the visible render.

## Out of scope

- Persisting the chosen color across a page reload (a separate, later
  feature).
- A custom (non-swatch) color input.

## Alternatives considered

A DOM-attribute-only test (`element.style.color` equality) was considered
and rejected for the live-render checkpoint item specifically: the whole
point of this feature is the pixel the user sees, and a passing attribute
assertion does not prove the browser actually painted it.

## Operational readiness

A pure front-end change to one existing page; no migration, no deployed
service change.

## Open questions

None.
