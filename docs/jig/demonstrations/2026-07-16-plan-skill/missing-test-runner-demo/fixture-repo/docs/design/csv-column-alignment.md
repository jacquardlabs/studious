# Design: add right-alignment for numeric columns to the CSV formatter

Fixture design doc, written solely to host this fix cycle's
missing-test-runner `DESIGN GAP` demonstration. Not a real feature.

## Problem & persona

A user of `disposable-report-formatter`'s CSV-to-Markdown conversion gets
left-aligned columns even when a column is entirely numeric, which reads
poorly once rendered.

## Proposed design

Detect columns where every body cell parses as a number and emit `---:`
(right-aligned) instead of `---` for that column's separator row.

## User journey

1. User runs `format_csv_as_markdown` against a CSV with a numeric column.
2. The emitted Markdown table's separator row right-aligns that column.
3. A checkpoint item verifies this with a **test-backed** unit test
   asserting the separator row's exact string for a fixture CSV -- this is
   a pure function with no UI surface, so a `test-backed` item (not
   `probe`) is the correct, honestly-representative tier here.

## Out of scope

- Locale-specific number formatting (thousands separators, decimals).
- Non-numeric alignment hints (e.g. explicit `:---:` for headers).

## Alternatives considered

N/A -- fixture doc, single approach.

## Operational readiness

A pure function change to one script; no migration, no deployed service.

## Open questions

None.
