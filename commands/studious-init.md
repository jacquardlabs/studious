---
description: Initialize Studious in the current project — creates PRODUCT.md, DESIGN.md, scaffolds review directories, and configures CLAUDE.md
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit, WebFetch
---

# Initialize product review workflow

Set up the full product review workflow in this project. This creates the context documents that all review agents depend on.

## Step 1 — Check current state

Before creating anything, check what already exists:
- Does PRODUCT.md exist? Is it populated or empty?
- Does DESIGN.md exist? Is it populated or empty?
- Does README.md exist?
- Does CLAUDE.md exist?
- Do any `docs/` review directories exist?

Report what you found and what you'll create vs skip.

## Step 2 — Create PRODUCT.md (if needed)

If PRODUCT.md doesn't exist, create it by copying the template that ships with the plugin. Copy it verbatim rather than inlining a second copy here — `templates/PRODUCT.md` is the single source of truth:

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/PRODUCT.md" PRODUCT.md
```

(`${CLAUDE_PLUGIN_ROOT}` is substituted to the plugin's install path before you read this. If the copy fails because it didn't resolve, locate `templates/PRODUCT.md` inside the plugin install with Glob and copy its contents — do not re-inline a template here.)

Then populate it as part of init — run the `/extract-product-context` workflow inline now. Don't stop and hand this back as a separate step; extract the product context from the codebase and continue. (Users can re-run `/extract-product-context` on its own later to refresh.)

## Step 3 — Create DESIGN.md (if needed)

If DESIGN.md doesn't exist, create it by copying the template that ships with the plugin (`templates/DESIGN.md`, the single source of truth — copy it verbatim rather than inlining a second copy here). DESIGN.md documents the product's *interface* conventions — the user-facing surface, whatever it is (web UI, CLI, TUI, REST API, HTML/email report) — not just visual design. It is distinct from CLAUDE.md, which documents how the code is written internally.

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/DESIGN.md" DESIGN.md
```

(Same fallback as Step 2: if `${CLAUDE_PLUGIN_ROOT}` didn't resolve and the copy fails, locate `templates/DESIGN.md` inside the plugin install with Glob and copy its contents — do not re-inline a template here.)

Then populate it as part of init — run the `/extract-design-system` workflow inline now. It detects which surfaces the product actually has and extracts the conventions for each; a non-visual product (CLI, API, plugin) gets a real interface doc, and a pure library gets an honest minimal one. Don't stop and hand this back as a separate step; extract and continue. (Users can re-run `/extract-design-system` on its own later to refresh.)

## Step 4 — Create README.md (if needed)

If README.md already exists, skip this step — leave it alone and tell the user to run `/deep-review readme` to check it for drift. Never overwrite an existing README.

If README.md doesn't exist, generate one now. PRODUCT.md exists at this point, so draw from it directly:

- **Source the content** from PRODUCT.md (what the product does, who it's for), the codebase (install/run commands, real file paths, config, `.env.example`), and the package manifest (name, scripts, license).
- **Match the project's voice.** Follow CLAUDE.md's writing-style guidance if present. Lead with what the product does and why. Keep it lean and direct.
- **No template decoration.** No emoji headers, no decorative badges, no marketing fluff. Standard Markdown, real headers, code blocks with language labels.
- **Only claim what's true.** Every command, path, and filename must match the codebase. Don't invent placeholders or aspirational features.

Cover, at minimum: what it is, install, a runnable usage example, and license. Write the file, then flag it for the user's review — the same way PRODUCT.md needs a human pass.

## Step 5 — Scaffold review directories

Create these directories if they don't exist:
- `docs/studious/health-reviews/`
- `docs/studious/interface-reviews/`
- `docs/studious/architecture-reviews/`
- `docs/studious/product-reviews/`
- `docs/studious/readme-reviews/`

Add a `.gitkeep` to each empty directory so they're tracked in git.

## Step 6 — Update CLAUDE.md

If CLAUDE.md exists, append the review workflow section (if not already present). If it doesn't exist, create it with just this section. Check for existing content first — don't duplicate.

Add this section:

```markdown
## Review workflow

### Context documents

- **PRODUCT.md** — product context, personas, principles, feature map. Read before any product decision.
- **DESIGN.md** — the interface design system: the product's user-facing surface(s) — web UI, CLI, TUI, API, or report — covering the semantic palette, vocabulary, formatting, and per-surface conventions. Read before changing anything users see. (CLAUDE.md owns *how the code is written*; DESIGN.md owns *the user-facing surface*.)

### Code conventions

Language conventions `code-auditor` enforces at `/gate-audit`. Document the rules and any deliberate deviations here — they override Studious's built-in idiom rubric.

- **<language>** — <conventions, e.g. "Python 3.11+. Prefer comprehensions, generator expressions, and stdlib (functools, itertools, collections) over explicit loops. Type hints required.">
- **Linter** — <the idiom linter and its rule selection, e.g. "Ruff with C4,SIM,PERF,B,RUF,PIE; run `ruff check` before pushing.">
- **Deliberate deviations** — <conventions you intentionally break and why, e.g. "explicit loops in hot paths.">

### Quality gates

| Gate | When | Command |
|------|------|---------|
| Should we build? | Before any engineering | `/gate-should-we-build [idea]` |
| Design review | After design doc, before implementation | `/gate-design-review` |
| Audit | After implementation, before acceptance | `/gate-audit` |
| Acceptance | After audit passes, before merge | `/gate-acceptance` |

### Periodic reviews

| Review | Cadence | Command |
|--------|---------|---------|
| Codebase health | Weekly or pre-milestone | `/deep-review codebase` |
| Interface health | Monthly or post-UI-sprint | `/deep-review interface` |
| Architecture | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | Monthly | `/deep-review product` |
| README drift | After a release or feature batch | `/deep-review readme` |
| All reviews + summary | As needed | `/deep-review` |

### After each review

1. Fix any **critical** findings before the next feature
2. File **important** findings as tasks to address this cycle
3. Track **minor** findings — they compound if ignored
4. Update context docs if the review surfaced changes:
   - `/deep-review product` updates PRODUCT.md
   - `/deep-review interface` updates DESIGN.md
   - `/deep-review architecture` updates CLAUDE.md
   - `/deep-review readme` proposes a README.md diff
```

When writing the **Code conventions** block, detect the project's primary language(s) from the codebase and pre-fill sensible defaults plus the matching idiom linter — Ruff for Python, ESLint/Biome for JS/TS, golangci-lint for Go, Clippy for Rust, RuboCop for Ruby — then flag it for the user to refine.

## Step 7 — Summary

Report what was created, what was populated, and what the user should review:
- PRODUCT.md — auto-populated sections and sections that need human input
- DESIGN.md — auto-populated sections and inconsistencies found
- README.md — created from scratch, or skipped because one already exists
- CLAUDE.md — sections added
- Review directories created

Note that the plugin's PR-time gate reminder is already active (it ships with Studious as a `PreToolUse` hook — no per-project wiring needed) and fires a non-blocking confirmation when you run `gh pr create`.

Suggest the user review PRODUCT.md first (product principles and "not building" sections need human judgment), then DESIGN.md (anti-patterns section needs human input), then README.md if one was generated.
