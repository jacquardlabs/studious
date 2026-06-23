---
description: Extract the interface design system from the existing codebase and populate DESIGN.md
allowed-tools: Read, Glob, Grep, Bash, Task, Write
---

# Extract interface design system from codebase

Analyze the existing codebase to discover the actual interface conventions already embedded in the code — across whatever surfaces the product exposes (web UI, CLI, TUI, REST API, HTML/email report). Do not invent or suggest — document what IS, including inconsistencies.

DESIGN.md documents the *user-facing surface*. It is not CLAUDE.md, which documents *how the code is written* (idioms, linters, internal style). When a convention is about command/flag naming, output formats, status codes, error envelopes, or display labels, it belongs here. When it's about loop style or type hints, it belongs in CLAUDE.md.

Read DESIGN.md first. If it already has content, you're updating it. If it's the blank template, you're populating it from scratch.

## Step 1 — Detect the surface set

Before extracting anything, determine which user-facing surfaces this product has. A product often has more than one (a CLI tool may also ship a TUI and an HTML report). Each surface maps to a fixed token (the same set DESIGN.md's Surfaces table uses): `web` | `cli` | `tui` | `api` | `report` | `plugin` | `library`. Detect from:

- **Dependency manifest** (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`):
  - `web`: React/Vue/Svelte/Angular/Next, Tailwind, styled-components, a CSS pipeline
  - `cli`: `click`/`rich-click`/`argparse`/`typer` (Python), `commander`/`yargs` (JS), `cobra` (Go), `clap` (Rust)
  - `plugin`: a `.claude-plugin/plugin.json` with `commands/`, `agents/`, `skills/` dirs (a Claude Code plugin), or a comparable "the product *is* a set of prompts/commands" layout
  - `tui`: `textual`/`urwid`/`blessed` (Python), `ink` (JS), `bubbletea` (Go), `ratatui` (Rust)
  - `api`: `fastapi`/`flask`/`django-rest`/`express`/`gin`/`axum`
  - `report`: `jinja2`/templating engines producing HTML/PDF/email
- **Module/file layout**: `src/app` or `pages/`/`app/` (web), `cli.py`/`__main__.py` (cli), `commands/`+`agents/` (plugin), `*_tui.py` (tui), route/controller files (api), `renderers/`/`templates/` (report).
- **Entry points**: `[project.scripts]` / `bin` in the manifest (CLI), a server entry (API/web).

Resolve the **set** of surfaces and each one's framework and entry point. A product with no external interface (a pure library) has *no* surface — say so, write a minimal DESIGN.md (the Surfaces table noting "library — no external interface; conventions live in CLAUDE.md"), and stop.

For each detected surface, run the matching extraction below. Sections 2–4 (semantic palette, vocabulary, formatting) apply to every surface and are extracted once, shared. Section 5 is per-surface.

## Step 2 — Extract the semantic palette (all surfaces)

The mapping of *state* (error, warning, success, info, neutral, emphasis) to *style*. Same meaning everywhere; rendered per surface.

- **Web**: grep for color usage tied to state — `text-red-*`/`bg-green-*` (Tailwind), semantic CSS custom properties (`--color-error`), theme tokens. Read tailwind.config.* or theme files for the defined palette.
- **CLI/TUI**: grep for terminal styles tied to state — `rich` styles (`bold red`, `dim`), ANSI codes, `click.style`, Textual CSS variables (`$error`, `$success`).
- Build a table: state → how each surface renders it. Flag states rendered inconsistently across surfaces (e.g. `red` for an error in the CLI but `orange` in the web UI) — cross-surface drift is the highest-value finding here.

## Step 3 — Extract the vocabulary (all surfaces)

The canonical user-facing names for the product's concepts. For multi-surface products this is the dominant concern: the same concept must read identically in every surface.

- Find the enums, constant dicts, or label maps that define display names (e.g. a `KIND_LABEL`/`STATUS_LABEL` dict, an enum with a `.label`).
- For each concept, record: its canonical display form, the **single source of truth** (file + symbol), and **every surface that consumes it** (grep the symbol's importers).
- Flag any surface that defines its own local copy of a label instead of importing the canonical one — that's a consistency bug waiting to happen.
- If no central source exists and each surface hardcodes its own strings, say so explicitly and list the divergences.

## Step 4 — Extract formatting conventions (all surfaces)

The output/number/string conventions — the non-visual analog of a type scale.

- Number/currency precision per context (grep format strings: `:.2f`, `:.3f`, `toFixed`, `Intl.NumberFormat`).
- Date/time formats.
- Any canonical headline/summary/verdict string and its single source.
- Truncation, pluralization, and casing rules.
- **Web also**: the visual type scale — font-family declarations and imports, every font-size in use (group into heading/body/caption), font-weights, line-heights. Note whether there's an intentional scale or ad-hoc sizes.

## Step 5 — Extract per-surface conventions

For each detected surface, extract its specific patterns.

### Web (if present)
- **Color tokens** — backgrounds, text, borders, accents (beyond the semantic palette). Flag one-off and near-duplicate colors.
- **Spacing** — base unit (4px/8px?), the scale, container max-widths, gap values. Note if ad hoc.
- **Component patterns** — buttons (variants/sizes/states), form inputs (label position, error display), cards, modals/dialogs, navigation, tables, loading states, empty states, error states, toasts. For each, note the file path of the best example (the reference implementation).
- **Responsive breakpoints** — defined vs. actually used; what changes at each.
- **Animation and motion** — transitions, keyframes, durations, easing; `prefers-reduced-motion` handling.
- **Accessibility baseline** — aria-* usage, alt text, skip-to-content link, focus styles.

### CLI (if present)
- Command/subcommand naming convention (verbs? nouns? `noun verb`?).
- Flag conventions — long/short forms, defaults, repeated patterns (`--json`, `--quiet`, `--verbose`).
- Output formats — table vs. plain vs. JSON; which command offers which; how tables are styled.
- Help-text style and structure.
- Exit-code conventions.
- Error-message style (prefix, color, where they go — stdout/stderr).
- Color/no-color handling (TTY detection, `NO_COLOR`).

### Plugin / prompt tooling (if present)
For a Claude Code plugin (or any product whose interface *is* a set of commands/prompts), the user-facing surface is the commands and their output contracts:
- Command naming convention (verb-first? `noun-verb`? prefix like `gate-`/`deep-`?).
- The verdict/output vocabulary each command emits — the canonical result tokens (e.g. `BUILD` / `BUILD SMALLER` / `DEFER` / `DON'T BUILD`; `PASS` / `FIX AND RE-AUDIT`). These are the plugin's most important interface contract; list each command's vocabulary and flag any drift between commands that should share one.
- Severity/tier vocabulary used in reports (e.g. Critical / Important / Minor) and whether it's consistent across commands.
- Report/output structure conventions (section ordering, summary-first, how findings are grouped).
- Natural-language trigger conventions (how skills shim to commands) and frontmatter conventions (description style, allowed-tools).

### TUI (if present)
- Framework and version.
- Screen/view structure and how navigation between them works.
- Modals/panels and how they're invoked and dismissed.
- Keybindings and the focus/navigation model.
- Status/header/footer lines and what they show.
- The test harness (e.g. Textual `Pilot`) and what coverage exists.

### API (if present)
- Resource naming and URL structure.
- Versioning scheme.
- Status-code conventions (what's returned when).
- Error-envelope shape (the canonical error response body).
- Pagination convention.
- Auth-header conventions and content types.

### Report / export (if present)
- The template files and rendering path.
- Structure of the output (sections, layout).
- How the shared semantic palette and vocabulary map onto this surface (e.g. a CSS class per concept).

## Step 6 — Find inconsistencies

The most important step. Compare everything you found, with cross-surface consistency first:

- **Cross-surface**: a concept that renders differently across surfaces (different label, different state color, different number precision). This is the failure mode a single-surface review can never catch.
- A surface defining a local copy of a value that has a canonical source elsewhere.
- Within the web surface: colors not in the palette, font-sizes off the scale, spacing off the grid, components that do the same thing but look different, patterns handled multiple ways.

## Step 7 — Write DESIGN.md

Populate each section of DESIGN.md with what you found, following the template's structure:

1. **Fill the Surfaces table** — surface, framework/tech, entry point — from Step 1. The Surface column must be one of the fixed tokens `web` | `cli` | `tui` | `api` | `report` | `plugin` | `library` (not free text like "Website" or "React app") — `/gate-audit` and `/deep-review` read this column to branch behavior, so it must be machine-readable. Put the framework name in the Framework / tech column instead.
2. **Semantic palette, Vocabulary, Formatting** — the shared layers from Steps 2–4. In the vocabulary table, always include the source-of-truth location and consumer list.
3. **Per-surface conventions** — one subsection per detected surface from Step 5. Delete the subsections for surfaces this product doesn't have.
4. **Document the dominant pattern**, then note deviations as HTML comments so they don't read as instructions.
5. **Leave the anti-patterns section empty** — that's for the developer, based on intent, not assumption.

Use exact values from the code (hex colors, pixel values, style names, label strings, file paths). Don't round, approximate, or "clean up" — document the real state so the developer can decide what to standardize. If a section has no discernible pattern, say so explicitly and list the values in use.

End with a summary of the top 5 inconsistencies that would have the most impact if standardized — leading with any cross-surface ones.
