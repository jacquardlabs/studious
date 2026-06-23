# Design system

<!-- This documents the product's INTERFACE conventions — the user-facing surface, not
     how the code is written internally (that's CLAUDE.md). A "surface" is any way users
     interact with the product: a web UI, a CLI, a TUI, a REST API, an HTML/email report.
     Most sections apply to every surface; some are surface-specific. Keep the surfaces
     this product actually has and delete the rest. A product with no external interface
     (a pure library) should say so here and keep this doc minimal. -->

## Surfaces

<!-- The set of user-facing surfaces this product exposes. /extract-design-system detects
     these; correct them if wrong — /gate-audit and /deep-review read this list to decide
     which checks apply. The Surface column is a fixed token (machine-read): use exactly one
     of `web` | `cli` | `tui` | `api` | `report` | `plugin` | `library`. Framework / tech and
     Entry point are free text. -->

| Surface | Framework / tech | Entry point |
|---------|------------------|-------------|
|         |                  |             |

## Semantic palette

<!-- State → style, shared across surfaces. The meaning is canonical; each surface renders
     it its own way (web: hex/token; CLI/TUI: terminal style like `bold red` or ANSI). -->

### States
<!-- e.g. error, warning, success, info, neutral/muted, emphasis -->

### Per-surface rendering
<!-- e.g. error → web `text-red-600` · CLI `bold red` · TUI `$error` -->

## Vocabulary

<!-- The canonical user-facing names for the product's concepts. For multi-surface products
     this is the most important section: the same concept must read identically everywhere.
     For each concept give its canonical display form, the single source of truth in code,
     and every surface that consumes it. -->

| Concept | Canonical display | Source of truth | Consumers |
|---------|-------------------|-----------------|-----------|
|         |                   |                 |           |

## Formatting

<!-- Output/number/string conventions — the non-visual analog of a type scale. e.g. number
     precision per context, date formats, the canonical headline/verdict string and its
     single source, truncation rules. Web also: type scale, font weights, line heights. -->

## Per-surface conventions

<!-- Surface-specific patterns. Keep only the surfaces listed above. -->

### Web
<!-- Color tokens (backgrounds, text, borders, accents); typography (families, scale,
     weights); spacing (base unit, scale, container widths); component patterns (buttons,
     inputs, cards, navigation, tables, loading/empty/error states); responsive breakpoints;
     animation and motion; accessibility baseline. -->

### CLI
<!-- Command/subcommand naming, flag conventions (long/short, defaults), output format
     (table/plain/json), help-text style, exit codes, error-message style, color/no-color. -->

### Plugin / prompt tooling
<!-- For a Claude Code plugin or prompt-as-product: command naming convention; the verdict/
     output vocabulary each command emits (e.g. BUILD / BUILD SMALLER / DEFER); the
     severity/tier vocabulary in reports (e.g. Critical / Important / Minor); report
     structure; natural-language trigger and frontmatter conventions. -->

### TUI
<!-- Framework, screen/view structure, modals/panels, keybindings, focus/navigation model,
     status/header lines, the test harness (e.g. Textual Pilot). -->

### API
<!-- Resource naming, URL/versioning scheme, status codes, error-envelope shape, pagination,
     auth-header conventions, content types. -->

### Report / export
<!-- HTML/PDF/email templates: structure, the rendering path, how the shared palette and
     vocabulary map onto this surface. -->

## Anti-patterns (do NOT do these)

<!-- Fill in as you discover patterns that hurt the product. Pin each to code where possible
     (e.g. "never define a local label dict — import the canonical one from models"). -->
